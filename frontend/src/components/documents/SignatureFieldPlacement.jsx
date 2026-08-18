import { useEffect, useMemo, useRef, useState } from 'react';
import {
  CalendarDays,
  FileSignature,
  RotateCcw,
} from 'lucide-react';
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist';
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

import { documentApi } from '../../api/documentApi.js';
import Button from '../ui/Button.jsx';

GlobalWorkerOptions.workerSrc = pdfWorker;

const FIELD_DIMENSIONS = {
  signature: { width: 0.30, height: 0.07 },
  date: { width: 0.19, height: 0.05 },
};

function clamp(value, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, value));
}

function rounded(value) {
  return Math.round(value * 10000) / 10000;
}

function signerName(recipient, employees, index) {
  const employee = employees.find((item) => (
    String(item.id) === String(recipient.employee_id)
  ));
  return employee?.full_name || `Signatory ${index + 1}`;
}

function PlacementPage({
  pdf,
  pageNumber,
  recipientFields,
  recipients,
  employees,
  selectedRecipient,
  activeFieldType,
  onPlace,
}) {
  const canvasRef = useRef(null);
  const pageRef = useRef(null);
  const [viewportSize, setViewportSize] = useState(null);

  useEffect(() => {
    let cancelled = false;
    let renderTask;

    pdf.getPage(pageNumber).then((page) => {
      if (cancelled) return;
      const viewport = page.getViewport({ scale: 1.05 });
      const canvas = canvasRef.current;
      const context = canvas.getContext('2d');
      const ratio = window.devicePixelRatio || 1;

      canvas.width = Math.floor(viewport.width * ratio);
      canvas.height = Math.floor(viewport.height * ratio);
      canvas.style.width = `${viewport.width}px`;
      canvas.style.height = `${viewport.height}px`;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      setViewportSize({ width: viewport.width, height: viewport.height });

      renderTask = page.render({ canvasContext: context, viewport });
      return renderTask.promise;
    }).catch(() => {});

    return () => {
      cancelled = true;
      renderTask?.cancel?.();
    };
  }, [pdf, pageNumber]);

  const place = (event) => {
    if (!viewportSize || selectedRecipient < 0) return;
    const rect = pageRef.current.getBoundingClientRect();
    const dimensions = FIELD_DIMENSIONS[activeFieldType];
    const x = clamp(
      ((event.clientX - rect.left) / rect.width) - (dimensions.width / 2),
      0,
      1 - dimensions.width,
    );
    const y = clamp(
      ((event.clientY - rect.top) / rect.height) - (dimensions.height / 2),
      0,
      1 - dimensions.height,
    );

    onPlace(selectedRecipient, {
      field_type: activeFieldType,
      label: activeFieldType === 'signature'
        ? 'Electronic signature'
        : 'Date signed',
      page_number: pageNumber,
      x: rounded(x),
      y: rounded(y),
      width: dimensions.width,
      height: dimensions.height,
      required: true,
    });
  };

  return (
    <div
      ref={pageRef}
      role="button"
      tabIndex={0}
      aria-label={`Place ${activeFieldType} field on PDF page ${pageNumber}`}
      className="relative mx-auto cursor-crosshair bg-white shadow-sm outline-none ring-blue-500 focus:ring-2"
      style={viewportSize || undefined}
      onClick={place}
      onKeyDown={() => {}}
    >
      <canvas ref={canvasRef} className="block" />
      {viewportSize && recipientFields.map(({ recipientIndex, field }) => {
        const selected = recipientIndex === selectedRecipient;
        return (
          <div
            key={`${recipientIndex}-${field.field_type}`}
            className={`pointer-events-none absolute overflow-hidden rounded-md border-2 px-2 py-1 shadow-sm ${selected ? 'border-blue-600 bg-blue-50/95 text-blue-950' : 'border-slate-400 bg-white/90 text-slate-700'}`}
            style={{
              left: `${field.x * 100}%`,
              top: `${field.y * 100}%`,
              width: `${field.width * 100}%`,
              minHeight: `${field.height * 100}%`,
            }}
          >
            <p className="truncate text-[9px] font-bold uppercase tracking-wide">
              {signerName(recipients[recipientIndex], employees, recipientIndex)}
            </p>
            <p className="truncate text-[10px] font-semibold">
              {field.field_type === 'signature' ? 'Signature' : 'Date signed'}
            </p>
          </div>
        );
      })}
    </div>
  );
}

export default function SignatureFieldPlacement({
  documentId,
  recipients,
  employees = [],
  onFieldsChange,
}) {
  const [pdfState, setPdfState] = useState({
    documentId: null,
    pdf: null,
    error: '',
  });
  const [selectedRecipientIndex, setSelectedRecipient] = useState(0);
  const [activeFieldType, setActiveFieldType] = useState('signature');

  const pdf =
    pdfState.documentId === documentId ? pdfState.pdf : null;

  const error =
    pdfState.documentId === documentId ? pdfState.error : '';

  const selectedRecipient = Math.min(
    selectedRecipientIndex,
    Math.max(0, recipients.length - 1),
  );

  useEffect(() => {
    let active = true;
    let objectUrl = '';
    let loadingTask;

    documentApi.content(documentId)
      .then((blob) => {
        if (!active) return;

        objectUrl = URL.createObjectURL(blob);

        loadingTask = getDocument({
          url: objectUrl,
          isEvalSupported: false,
          enableScripting: false,
        });

        loadingTask.promise
          .then((loaded) => {
            if (active) {
              setPdfState({
                documentId,
                pdf: loaded,
                error: '',
              });
            }
          })
          .catch(() => {
            if (active) {
              setPdfState({
                documentId,
                pdf: null,
                error: 'Unable to render this PDF for field placement.',
              });
            }
          });
      })
      .catch(() => {
        if (active) {
          setPdfState({
            documentId,
            pdf: null,
            error: 'Unable to load the PDF for field placement.',
          });
        }
      });

    return () => {
      active = false;
      loadingTask?.destroy?.();

      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [documentId]);

  const pageFields = useMemo(() => {
    const values = [];
    recipients.forEach((recipient, recipientIndex) => {
      (recipient.fields || []).forEach((field) => {
        values.push({ recipientIndex, field });
      });
    });
    return values;
  }, [recipients]);

  const placeField = (recipientIndex, field) => {
    const current = recipients[recipientIndex]?.fields || [];
    const next = [
      ...current.filter((item) => item.field_type !== field.field_type),
      field,
    ];
    onFieldsChange(recipientIndex, next);
    if (field.field_type === 'signature') setActiveFieldType('date');
  };

  const selectedFields = recipients[selectedRecipient]?.fields || [];
  const selectedHasSignature = selectedFields.some((field) => field.field_type === 'signature');
  const selectedHasDate = selectedFields.some((field) => field.field_type === 'date');

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
      <div className="border-b border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-semibold text-slate-950">Place signature fields</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Select a signatory and field type, then click the PDF to place or reposition that field. Each signatory needs one signature and one date field.
            </p>
          </div>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={() => onFieldsChange(selectedRecipient, [])}
          >
            <RotateCcw size={14} /> Clear selected signer
          </Button>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
          <div className="flex flex-wrap gap-2">
            {recipients.map((recipient, index) => {
              const fields = recipient.fields || [];
              const complete = ['signature', 'date'].every((type) => (
                fields.some((field) => field.field_type === type)
              ));
              return (
                <button
                  key={`${recipient.employee_id || 'recipient'}-${index}`}
                  type="button"
                  onClick={() => setSelectedRecipient(index)}
                  className={`rounded-lg border px-3 py-2 text-left text-xs ${index === selectedRecipient ? 'border-blue-500 bg-blue-50 text-blue-950' : 'border-slate-200 bg-white text-slate-700'}`}
                >
                  <span className="block font-semibold">
                    {signerName(recipient, employees, index)}
                  </span>
                  <span className="mt-0.5 block text-[10px]">
                    {complete ? 'Signature + date placed' : 'Fields incomplete'}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setActiveFieldType('signature')}
              className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold ${activeFieldType === 'signature' ? 'border-blue-600 bg-blue-600 text-white' : 'border-slate-200 bg-white text-slate-700'}`}
            >
              <FileSignature size={14} />
              {selectedHasSignature ? 'Move signature' : 'Place signature'}
            </button>
            <button
              type="button"
              onClick={() => setActiveFieldType('date')}
              className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold ${activeFieldType === 'date' ? 'border-blue-600 bg-blue-600 text-white' : 'border-slate-200 bg-white text-slate-700'}`}
            >
              <CalendarDays size={14} />
              {selectedHasDate ? 'Move date' : 'Place date'}
            </button>
          </div>
        </div>
      </div>

      {!pdf ? (
        <div className="grid min-h-80 place-items-center p-8 text-sm text-slate-500">
          Preparing PDF field editor…
        </div>
      ) : (
        <div className="max-h-[720px] space-y-6 overflow-auto bg-slate-200/70 p-5">
          {Array.from({ length: pdf.numPages }, (_, index) => index + 1).map((pageNumber) => (
            <PlacementPage
              key={pageNumber}
              pdf={pdf}
              pageNumber={pageNumber}
              recipientFields={pageFields.filter(({ field }) => field.page_number === pageNumber)}
              recipients={recipients}
              employees={employees}
              selectedRecipient={selectedRecipient}
              activeFieldType={activeFieldType}
              onPlace={placeField}
            />
          ))}
        </div>
      )}
    </section>
  );
}
