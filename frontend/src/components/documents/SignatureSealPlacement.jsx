import {
  useEffect,
  useRef,
  useState,
} from 'react';
import {
  ChevronLeft,
  ChevronRight,
  Save,
  Upload,
} from 'lucide-react';
import {
  getDocument,
  GlobalWorkerOptions,
} from 'pdfjs-dist';
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

import { signatureApi } from '../../api/signatureApi.js';
import Button from '../ui/Button.jsx';

GlobalWorkerOptions.workerSrc = pdfWorker;

const ALLOWED_IMAGE_TYPES = new Set([
  'image/png',
  'image/jpeg',
  'image/webp',
]);

const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const MIN_SEAL_WIDTH = 0.08;
const MIN_SEAL_HEIGHT = 0.04;

function clamp(value, minimum, maximum) {
  return Math.max(
    minimum,
    Math.min(maximum, value),
  );
}

function rounded(value) {
  return Math.round(value * 10000) / 10000;
}

function placementFromSeal(seal) {
  if (
    !seal
    || seal.page_number == null
    || seal.x == null
    || seal.y == null
    || seal.width == null
    || seal.height == null
  ) {
    return null;
  }

  return {
    page_number: seal.page_number,
    x: seal.x,
    y: seal.y,
    width: seal.width,
    height: seal.height,
  };
}

function SealOverlay({
  placement,
  pageRef,
  preview,
  onChange,
}) {
  const interactionRef = useRef(null);

  const beginInteraction = (event, mode) => {
    if (!pageRef.current) return;

    event.preventDefault();
    event.stopPropagation();

    interactionRef.current = {
      mode,
      startClientX: event.clientX,
      startClientY: event.clientY,
      pageRect: pageRef.current.getBoundingClientRect(),
      startPlacement: {
        ...placement,
      },
    };

    event.currentTarget
      .setPointerCapture?.(event.pointerId);
  };

  const moveInteraction = (event) => {
    const interaction = interactionRef.current;
    if (!interaction) return;

    event.preventDefault();
    event.stopPropagation();

    const {
      mode,
      pageRect,
      startClientX,
      startClientY,
      startPlacement,
    } = interaction;

    const dx = (
      event.clientX - startClientX
    ) / pageRect.width;

    const dy = (
      event.clientY - startClientY
    ) / pageRect.height;

    if (mode === 'move') {
      onChange({
        ...startPlacement,
        x: rounded(clamp(
          startPlacement.x + dx,
          0,
          1 - startPlacement.width,
        )),
        y: rounded(clamp(
          startPlacement.y + dy,
          0,
          1 - startPlacement.height,
        )),
      });

      return;
    }

    onChange({
      ...startPlacement,
      width: rounded(clamp(
        startPlacement.width + dx,
        MIN_SEAL_WIDTH,
        1 - startPlacement.x,
      )),
      height: rounded(clamp(
        startPlacement.height + dy,
        MIN_SEAL_HEIGHT,
        1 - startPlacement.y,
      )),
    });
  };

  const endInteraction = (event) => {
    if (!interactionRef.current) return;

    event.preventDefault();
    event.stopPropagation();

    interactionRef.current = null;

    event.currentTarget
      .releasePointerCapture?.(event.pointerId);
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Move company seal"
      className="absolute z-20 cursor-move touch-none overflow-hidden border-2 border-blue-600 bg-white/90 shadow-lg"
      style={{
        left: `${placement.x * 100}%`,
        top: `${placement.y * 100}%`,
        width: `${placement.width * 100}%`,
        height: `${placement.height * 100}%`,
      }}
      onPointerDown={(event) => (
        beginInteraction(event, 'move')
      )}
      onPointerMove={moveInteraction}
      onPointerUp={endInteraction}
      onPointerCancel={endInteraction}
      onClick={(event) => event.stopPropagation()}
      onKeyDown={() => {}}
    >
      {preview ? (
        <img
          src={preview}
          alt="Company seal preview"
          className="h-full w-full object-fill"
          draggable={false}
        />
      ) : (
        <span className="grid h-full w-full place-items-center px-2 text-center text-xs font-semibold text-slate-600">
          Company seal
        </span>
      )}

      <span
        role="presentation"
        className="absolute bottom-0 right-0 h-4 w-4 cursor-se-resize border-l border-t border-blue-600 bg-white"
        onPointerDown={(event) => (
          beginInteraction(event, 'resize')
        )}
        onPointerMove={moveInteraction}
        onPointerUp={endInteraction}
        onPointerCancel={endInteraction}
      />
    </div>
  );
}

export default function SignatureSealPlacement({
  request,
  seal = null,
  loading = false,
  onSealChange,
  onPlacementSaved,
}) {
  const canvasRef = useRef(null);
  const pageRef = useRef(null);

  const [pdf, setPdf] = useState(null);
  const [pdfError, setPdfError] = useState('');
  const [currentPage, setCurrentPage] = useState(
    seal?.page_number || 1,
  );
  const [viewportSize, setViewportSize] = useState(null);
  const [preview, setPreview] = useState('');
  const [sealRecord, setSealRecord] = useState(seal);
  const [placement, setPlacement] = useState(
    () => placementFromSeal(seal),
  );
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const signedArtifactId = request?.signed_document?.id;

  useEffect(() => {
    let active = true;
    let loadingTask;

    setPdf(null);
    setPdfError('');

    if (!request?.id || !signedArtifactId) {
      setPdfError(
        'The completed signed PDF is not available for seal placement.',
      );

      return undefined;
    }

    signatureApi.artifact(
      request.id,
      signedArtifactId,
    )
      .then(async (response) => {
        const blob = response.data;
        const pdfData = new Uint8Array(
          await blob.arrayBuffer(),
        );

        if (!active) return;

        loadingTask = getDocument({
          data: pdfData,
          isEvalSupported: false,
          enableScripting: false,
        });

        const loadedPdf = await loadingTask.promise;

        if (!active) return;

        setPdf(loadedPdf);
        setCurrentPage((page) => clamp(
          page,
          1,
          loadedPdf.numPages,
        ));
      })
      .catch(() => {
        if (!active) return;

        setPdfError(
          'Unable to load the signed PDF for company seal placement.',
        );
      });

    return () => {
      active = false;
      loadingTask?.destroy?.();
    };
  }, [
    request?.id,
    signedArtifactId,
  ]);

  useEffect(() => {
    if (!request?.id || !seal?.image_original_filename) {
      setPreview('');
      return undefined;
    }

    let active = true;

    signatureApi.sealImage(request.id)
      .then((response) => {
        if (!active) return;

        const reader = new FileReader();

        reader.onload = () => {
          if (!active) return;

          setPreview(
            typeof reader.result === 'string'
              ? reader.result
              : '',
        );
      };

      reader.onerror = () => {
        if (active) setPreview('');
      };

      reader.readAsDataURL(response.data);
    })
      .catch(() => {
        if (active) setPreview('');
      });

    return () => {
      active = false;
    };
  }, [
    request?.id,
    seal?.id,
    seal?.image_original_filename,
  ]);

  useEffect(() => {
    if (!pdf) return undefined;

    let cancelled = false;
    let renderTask;

    pdf.getPage(currentPage)
      .then((page) => {
        if (cancelled) return null;

        const viewport = page.getViewport({
          scale: 1.05,
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
      .catch(() => {
        if (!cancelled) {
          setPdfError(
            'Unable to render this signed PDF page.',
          );
        }
      });

    return () => {
      cancelled = true;
      renderTask?.cancel?.();
    };
  }, [
    currentPage,
    pdf,
  ]);

  const uploadSeal = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setMessage('');

    if (!ALLOWED_IMAGE_TYPES.has(file.type)) {
      setMessage(
        'Choose a PNG, JPEG or WebP company seal image.',
      );
      return;
    }

    if (file.size > MAX_IMAGE_BYTES) {
      setMessage(
        'The company seal image must not exceed 5 MB.',
      );
      return;
    }

    const reader = new FileReader();

    reader.onload = () => {
      setPreview(
        typeof reader.result === 'string'
          ? reader.result
          : '',
      );
    };

    reader.readAsDataURL(file);

    setBusy(true);

    try {
      const response = await signatureApi.uploadSealImage(
        request.id,
        file,
      );

      const uploadedSeal = response.data;

      setSealRecord(uploadedSeal);

      const storedPlacement = placementFromSeal(
        uploadedSeal,
      );

      if (storedPlacement) {
        setPlacement(storedPlacement);
        setCurrentPage(storedPlacement.page_number);
      } else {
        setPlacement({
          page_number: currentPage,
          x: 0.68,
          y: 0.78,
          width: 0.22,
          height: 0.12,
        });
      }

      setMessage('Company seal image uploaded.');
      onSealChange?.(uploadedSeal);
    } catch (error) {
      setMessage(
        error.error?.message
        || 'Unable to upload the company seal image.',
      );
    } finally {
      setBusy(false);
    }
  };

  const placeSeal = (event) => {
    if (
      !pageRef.current
      || (!preview && !sealRecord?.image_original_filename)
    ) {
      return;
    }

    const rect = pageRef.current
      .getBoundingClientRect();

    const width = placement?.width || 0.22;
    const height = placement?.height || 0.12;

    const x = clamp(
      (
        (event.clientX - rect.left)
        / rect.width
      ) - (width / 2),
      0,
      1 - width,
    );

    const y = clamp(
      (
        (event.clientY - rect.top)
        / rect.height
      ) - (height / 2),
      0,
      1 - height,
    );

    setPlacement({
      page_number: currentPage,
      x: rounded(x),
      y: rounded(y),
      width: rounded(width),
      height: rounded(height),
    });
  };

  const savePlacement = async () => {
    if (!placement) {
      setMessage(
        'Upload and place the company seal before saving.',
      );
      return;
    }

    setBusy(true);
    setMessage('');

    try {
      const response = await signatureApi.updateSealPlacement(
        request.id,
        placement,
      );

      setSealRecord(response.data);
      setMessage('Company seal placement saved.');
      onPlacementSaved?.(response.data);
    } catch (error) {
      setMessage(
        error.error?.message
        || 'Unable to save the company seal placement.',
      );
    } finally {
      setBusy(false);
    }
  };

  if (pdfError) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {pdfError}
      </div>
    );
  }

  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-slate-100">
      <div className="border-b border-slate-200 bg-white p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="font-semibold text-slate-950">
              Place company seal
            </p>
            <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-500">
              Upload the approved seal image, then position it on the
              completed signed PDF. Placement is saved separately from
              final seal application.
            </p>
          </div>

          <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800">
            <Upload size={15} />
            Upload seal image
            <input
              type="file"
              aria-label="Company seal image"
              accept="image/png,image/jpeg,image/webp"
              className="sr-only"
              disabled={loading || busy}
              onChange={uploadSeal}
            />
          </label>
        </div>

        {sealRecord?.image_original_filename && (
          <p className="mt-3 text-xs text-slate-500">
            Uploaded: {sealRecord.image_original_filename}
          </p>
        )}

        {message && (
          <p className="mt-3 text-sm text-slate-600">
            {message}
          </p>
        )}
      </div>

      {!pdf ? (
        <div className="grid min-h-96 place-items-center p-8 text-sm text-slate-500">
          Preparing signed PDF…
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-2">
            <div className="flex items-center gap-2">
              <button
                type="button"
                aria-label="Previous PDF page"
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage(
                  (page) => Math.max(1, page - 1),
                )}
                className="rounded-md border border-slate-200 p-2 text-slate-600 disabled:opacity-40"
              >
                <ChevronLeft size={15} />
              </button>

              <span className="text-xs font-semibold text-slate-700">
                Page {currentPage} of {pdf.numPages}
              </span>

              <button
                type="button"
                aria-label="Next PDF page"
                disabled={currentPage >= pdf.numPages}
                onClick={() => setCurrentPage(
                  (page) => Math.min(
                    pdf.numPages,
                    page + 1,
                  ),
                )}
                className="rounded-md border border-slate-200 p-2 text-slate-600 disabled:opacity-40"
              >
                <ChevronRight size={15} />
              </button>
            </div>

            <Button
              type="button"
              size="sm"
              variant="secondary"
              disabled={loading || busy || !placement}
              onClick={savePlacement}
            >
              <Save size={14} />
              Save seal placement
            </Button>
          </div>

          <div className="max-h-[760px] overflow-auto bg-slate-200/70 p-5">
            <div
              ref={pageRef}
              role="button"
              tabIndex={0}
              aria-label={`Place company seal on PDF page ${currentPage}`}
              className="relative mx-auto cursor-crosshair bg-white shadow-lg outline-none ring-blue-500 focus:ring-2"
              style={viewportSize || undefined}
              onClick={placeSeal}
              onKeyDown={() => {}}
            >
              <canvas
                ref={canvasRef}
                className="block"
              />

              {(
                viewportSize
                && placement
                && placement.page_number === currentPage
                && (
                  preview
                  || sealRecord?.image_original_filename
                )
              ) && (
                <SealOverlay
                  placement={placement}
                  pageRef={pageRef}
                  preview={preview}
                  onChange={setPlacement}
                />
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
