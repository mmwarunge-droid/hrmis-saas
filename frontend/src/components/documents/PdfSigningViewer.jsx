import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { FileText } from 'lucide-react';
import {
  getDocument,
  GlobalWorkerOptions,
} from 'pdfjs-dist';
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

GlobalWorkerOptions.workerSrc = pdfWorker;

function fieldLabel(field) {
  if (field.label) return field.label;

  switch (field.field_type) {
    case 'signature':
      return 'Sign here';
    case 'date':
      return 'Date signed';
    case 'name':
      return 'Full name';
    case 'initials':
      return 'Initials';
    default:
      return 'Text';
  }
}

function fieldPreview(
  field,
  fieldValues,
) {
  const value = (
    fieldValues?.[String(field.id)]
    ?? field.value
  );

  if (String(value ?? '').trim()) {
    return String(value).trim();
  }

  switch (field.field_type) {
    case 'signature':
      return 'Your signature';

    case 'date':
      return 'Set on submission';

    case 'name':
      return 'Official profile name';

    default:
      return (
        field.placeholder
        || 'Complete this field'
      );
  }
}

function PdfPage({
  pdf,
  pageNumber,
  fields,
  activeFieldId,
  fieldValues,
  onFieldSelect,
}) {
  const canvasRef = useRef(null);
  const [viewportSize, setViewportSize] = (
    useState(null)
  );

  useEffect(() => {
    let cancelled = false;
    let renderTask;

    pdf.getPage(pageNumber)
      .then((page) => {
        if (cancelled) return null;

        const viewport = page.getViewport({
          scale: 1.25,
        });

        const canvas = canvasRef.current;
        if (!canvas) return null;

        const context = canvas.getContext('2d');
        const ratio = window.devicePixelRatio || 1;

        canvas.width = Math.floor(
          viewport.width * ratio,
        );

        canvas.height = Math.floor(
          viewport.height * ratio,
        );

        canvas.style.width = `${viewport.width}px`;
        canvas.style.height = `${viewport.height}px`;

        context.setTransform(
          ratio,
          0,
          0,
          ratio,
          0,
          0,
        );

        setViewportSize({
          width: viewport.width,
          height: viewport.height,
        });

        renderTask = page.render({
          canvasContext: context,
          viewport,
        });

        return renderTask.promise;
      })
      .catch(() => {});

    return () => {
      cancelled = true;
      renderTask?.cancel?.();
    };
  }, [
    pdf,
    pageNumber,
  ]);

  return (
    <div
      className="relative mx-auto bg-white shadow-sm"
      style={viewportSize || undefined}
      data-page-number={pageNumber}
    >
      <canvas
        ref={canvasRef}
        className="block"
      />

      {viewportSize && fields.map((field) => {
        const active = (
          String(field.id)
          === String(activeFieldId)
        );

        return (
          <button
            id={`signing-field-${field.id}`}
            key={field.id}
            type="button"
            aria-label={`Select ${fieldLabel(field)}`}
            onClick={() => onFieldSelect?.(
              String(field.id),
            )}
            className={`absolute overflow-hidden rounded-md border-2 px-2 py-1 text-left shadow-sm transition ${
              active
                ? 'z-20 border-blue-700 bg-blue-100 text-blue-950 ring-4 ring-blue-200'
                : 'z-10 border-blue-500 bg-blue-50/90 text-blue-950 hover:bg-blue-100'
            }`}
            style={{
              left: `${field.x * 100}%`,
              top: `${field.y * 100}%`,
              width: `${field.width * 100}%`,
              minHeight: `${field.height * 100}%`,
            }}
          >
            <p className="truncate text-[9px] font-bold uppercase tracking-wide text-blue-700">
              {fieldLabel(field)}
              {field.required ? ' · Required' : ''}
            </p>

            <p className={`truncate ${
              field.field_type === 'signature'
                ? 'font-serif text-lg italic'
                : 'text-xs font-semibold'
            }`}
            >
              {fieldPreview(
                field,
                fieldValues,
              )}
            </p>
          </button>
        );
      })}
    </div>
  );
}

export default function PdfSigningViewer({
  url,
  fields = [],
  activeFieldId = null,
  fieldValues = {},
  onFieldSelect,
}) {
  const [loadState, setLoadState] = useState({
    source: null,
    pdf: null,
    error: '',
  });

  const pdf = (
    loadState.source === url
      ? loadState.pdf
      : null
  );

  const error = (
    loadState.source === url
      ? loadState.error
      : ''
  );

  useEffect(() => {
    if (!url) return undefined;

    let active = true;

    const source = (
      typeof url === 'string'
        ? url
        : new Uint8Array(url)
    );

    const loadingTask = getDocument({
      ...(typeof source === 'string'
        ? { url: source }
        : { data: source }),
      isEvalSupported: false,
      enableScripting: false,
    });

    loadingTask.promise
      .then((loaded) => {
        if (!active) return;

        setLoadState({
          source: url,
          pdf: loaded,
          error: '',
        });
      })
      .catch(() => {
        if (!active) return;

        setLoadState({
          source: url,
          pdf: null,
          error: 'Unable to render the signing PDF.',
        });
      });

    return () => {
      active = false;
      loadingTask.destroy?.();
    };
  }, [url]);

  useEffect(() => {
    if (!activeFieldId || !pdf) {
      return undefined;
    }

    const frame = window.requestAnimationFrame(
      () => {
        document
          .getElementById(
            `signing-field-${activeFieldId}`,
          )
          ?.scrollIntoView({
            block: 'center',
            inline: 'center',
            behavior: 'smooth',
          });
      },
    );

    return () => (
      window.cancelAnimationFrame(frame)
    );
  }, [
    activeFieldId,
    pdf,
  ]);

  const pages = useMemo(
    () => (
      pdf
        ? Array.from(
          { length: pdf.numPages },
          (_, index) => index + 1,
        )
        : []
    ),
    [pdf],
  );

  if (error) {
    return (
      <div className="grid min-h-[65vh] place-items-center text-sm text-red-600">
        {error}
      </div>
    );
  }

  if (!pdf) {
    return (
      <div className="grid min-h-[65vh] place-items-center text-sm text-slate-500">
        <div className="text-center">
          <FileText
            className="mx-auto mb-2"
            size={24}
          />
          Preparing secure PDF viewer…
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 overflow-auto bg-slate-200/70 p-5">
      {pages.map((pageNumber) => (
        <PdfPage
          key={pageNumber}
          pdf={pdf}
          pageNumber={pageNumber}
          fields={fields.filter(
            (field) => (
              field.page_number === pageNumber
            ),
          )}
          activeFieldId={activeFieldId}
          fieldValues={fieldValues}
          onFieldSelect={onFieldSelect}
        />
      ))}
    </div>
  );
}
