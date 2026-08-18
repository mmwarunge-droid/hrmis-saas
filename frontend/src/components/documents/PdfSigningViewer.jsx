import { useEffect, useMemo, useRef, useState } from 'react';
import { FileText } from 'lucide-react';
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist';
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

GlobalWorkerOptions.workerSrc = pdfWorker;

function PdfPage({ pdf, pageNumber, fields }) {
  const canvasRef = useRef(null);
  const [viewportSize, setViewportSize] = useState(null);

  useEffect(() => {
    let cancelled = false;
    let renderTask;

    pdf.getPage(pageNumber).then((page) => {
      if (cancelled) return;
      const viewport = page.getViewport({ scale: 1.25 });
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

  return (
    <div
      className="relative mx-auto bg-white shadow-sm"
      style={viewportSize || undefined}
      data-page-number={pageNumber}
    >
      <canvas ref={canvasRef} className="block" />
      {viewportSize && fields.map((field) => (
        <div
          key={field.id}
          className="pointer-events-none absolute rounded-md border-2 border-blue-500 bg-blue-50/90 px-2 py-1 text-blue-950 shadow-sm"
          style={{
            left: `${field.x * 100}%`,
            top: `${field.y * 100}%`,
            width: `${field.width * 100}%`,
            minHeight: `${field.height * 100}%`,
          }}
        >
          <p className="text-[9px] font-bold uppercase tracking-wide text-blue-700">
            {field.field_type === 'signature' ? 'Sign here' : 'Date signed'}
          </p>
          {field.field_type === 'signature' ? (
            <p className="truncate font-serif text-lg italic">Your signature</p>
          ) : (
            <p className="text-xs font-semibold">Set on submission</p>
          )}
        </div>
      ))}
    </div>
  );
}

export default function PdfSigningViewer({ url, fields = [] }) {
  const [loadState, setLoadState] = useState({
    url: '',
    pdf: null,
    error: '',
  });

  const pdf = loadState.url === url ? loadState.pdf : null;
  const error = loadState.url === url ? loadState.error : '';

  useEffect(() => {
    if (!url) return undefined;

    let active = true;

    const loadingTask = getDocument({
      url,
      isEvalSupported: false,
      enableScripting: false,
    });

    loadingTask.promise
      .then((loaded) => {
        if (active) {
          setLoadState({
            url,
            pdf: loaded,
            error: '',
          });
        }
      })
      .catch(() => {
        if (active) {
          setLoadState({
            url,
            pdf: null,
            error: 'Unable to render the signing PDF.',
          });
        }
      });

    return () => {
      active = false;
      loadingTask.destroy?.();
    };
  }, [url]);

  const pages = useMemo(
    () => (pdf ? Array.from({ length: pdf.numPages }, (_, index) => index + 1) : []),
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
          <FileText className="mx-auto mb-2" size={24} />
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
          fields={fields.filter((field) => field.page_number === pageNumber)}
        />
      ))}
    </div>
  );
}
