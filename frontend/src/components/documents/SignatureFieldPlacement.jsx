import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  FileSignature,
  RotateCcw,
  Trash2,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import {
  getDocument,
  GlobalWorkerOptions,
} from 'pdfjs-dist';
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

import { documentApi } from '../../api/documentApi.js';
import Button from '../ui/Button.jsx';

GlobalWorkerOptions.workerSrc = pdfWorker;

const FIELD_TYPES = [
  {
    type: 'signature',
    label: 'Signature',
    defaultLabel: 'Electronic signature',
    width: 0.30,
    height: 0.07,
    required: true,
  },
  {
    type: 'date',
    label: 'Date',
    defaultLabel: 'Date signed',
    width: 0.19,
    height: 0.05,
    required: true,
  },
  {
    type: 'name',
    label: 'Name',
    defaultLabel: 'Full name',
    width: 0.27,
    height: 0.05,
    required: true,
  },
  {
    type: 'text',
    label: 'Text',
    defaultLabel: 'Text',
    width: 0.30,
    height: 0.05,
    required: true,
  },
  {
    type: 'initials',
    label: 'Initials',
    defaultLabel: 'Initials',
    width: 0.13,
    height: 0.05,
    required: true,
  },
];

const FIELD_META = Object.fromEntries(
  FIELD_TYPES.map((item) => [
    item.type,
    item,
  ]),
);

const PREFILL_OPTIONS = [
  {
    value: '',
    label: 'None — signatory enters value',
  },
  {
    value: 'employee.full_name',
    label: 'Employee full name',
  },
  {
    value: 'employee.email',
    label: 'Employee email',
  },
  {
    value: 'employee.initials',
    label: 'Employee initials',
  },
  {
    value: 'recipient.role_label',
    label: 'Signing role',
  },
];

const MIN_FIELD_WIDTH = 0.06;
const MIN_FIELD_HEIGHT = 0.035;
const MIN_ZOOM = 0.65;
const MAX_ZOOM = 1.75;

function clamp(value, minimum, maximum) {
  return Math.max(
    minimum,
    Math.min(maximum, value),
  );
}

function rounded(value) {
  return Math.round(value * 10000) / 10000;
}

function fieldMetadata(type) {
  return FIELD_META[type] || FIELD_META.text;
}

function signerName(
  recipient,
  employees,
  index,
) {
  const employee = employees.find((item) => (
    String(item.id)
    === String(recipient.employee_id)
  ));

  return (
    employee?.full_name
    || `Signatory ${index + 1}`
  );
}

function fieldDisplayName(field) {
  return (
    field.label
    || fieldMetadata(field.field_type).label
  );
}

function newField(type, pageNumber, x, y) {
  const metadata = fieldMetadata(type);

  return {
    field_type: type,
    label: metadata.defaultLabel,
    placeholder: null,
    prefill_key: null,
    page_number: pageNumber,
    x: rounded(x),
    y: rounded(y),
    width: metadata.width,
    height: metadata.height,
    required: metadata.required,
  };
}

function PageThumbnail({
  pdf,
  pageNumber,
  active,
  onSelect,
}) {
  const canvasRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    let renderTask;

    pdf.getPage(pageNumber)
      .then((page) => {
        if (cancelled) return null;

        const viewport = page.getViewport({
          scale: 0.16,
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
    pageNumber,
    pdf,
  ]);

  return (
    <button
      type="button"
      aria-label={`Go to PDF page ${pageNumber}`}
      onClick={() => onSelect(pageNumber)}
      className={`w-full rounded-lg border p-2 text-center transition ${
        active
          ? 'border-blue-500 bg-blue-50'
          : 'border-slate-200 bg-white hover:border-slate-300'
      }`}
    >
      <canvas
        ref={canvasRef}
        className="mx-auto block max-w-full"
      />
      <span className="mt-1 block text-[10px] font-semibold text-slate-600">
        Page {pageNumber}
      </span>
    </button>
  );
}

function FieldBox({
  field,
  fieldIndex,
  recipientIndex,
  recipient,
  employees,
  selected,
  pageRef,
  onSelect,
  onChange,
}) {
  const interactionRef = useRef(null);

  const beginInteraction = (
    event,
    mode,
  ) => {
    if (!pageRef.current) return;

    event.preventDefault();
    event.stopPropagation();

    onSelect(
      recipientIndex,
      fieldIndex,
    );

    interactionRef.current = {
      mode,
      startClientX: event.clientX,
      startClientY: event.clientY,
      pageRect: pageRef.current
        .getBoundingClientRect(),
      startField: {
        x: field.x,
        y: field.y,
        width: field.width,
        height: field.height,
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
      pageRect,
      startClientX,
      startClientY,
      startField,
      mode,
    } = interaction;

    const dx = (
      event.clientX - startClientX
    ) / pageRect.width;

    const dy = (
      event.clientY - startClientY
    ) / pageRect.height;

    if (mode === 'move') {
      onChange(
        recipientIndex,
        fieldIndex,
        {
          x: rounded(clamp(
            startField.x + dx,
            0,
            1 - startField.width,
          )),
          y: rounded(clamp(
            startField.y + dy,
            0,
            1 - startField.height,
          )),
        },
      );

      return;
    }

    const width = clamp(
      startField.width + dx,
      MIN_FIELD_WIDTH,
      1 - startField.x,
    );

    const height = clamp(
      startField.height + dy,
      MIN_FIELD_HEIGHT,
      1 - startField.y,
    );

    onChange(
      recipientIndex,
      fieldIndex,
      {
        width: rounded(width),
        height: rounded(height),
      },
    );
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
      aria-label={`Move ${fieldDisplayName(field)} field for ${signerName(
        recipient,
        employees,
        recipientIndex,
      )}`}
      className={`absolute touch-none overflow-hidden rounded-md border-2 px-2 py-1 shadow-sm ${
        selected
          ? 'z-20 cursor-move border-blue-600 bg-blue-50/95 text-blue-950'
          : 'z-10 cursor-move border-slate-400 bg-white/90 text-slate-700'
      }`}
      style={{
        left: `${field.x * 100}%`,
        top: `${field.y * 100}%`,
        width: `${field.width * 100}%`,
        height: `${field.height * 100}%`,
      }}
      onPointerDown={(event) => (
        beginInteraction(event, 'move')
      )}
      onPointerMove={moveInteraction}
      onPointerUp={endInteraction}
      onPointerCancel={endInteraction}
      onClick={(event) => {
        event.stopPropagation();

        onSelect(
          recipientIndex,
          fieldIndex,
        );
      }}
      onKeyDown={(event) => {
        if (
          event.key === 'Enter'
          || event.key === ' '
        ) {
          event.preventDefault();

          onSelect(
            recipientIndex,
            fieldIndex,
          );
        }
      }}
    >
      <p className="truncate text-[9px] font-bold uppercase tracking-wide">
        {signerName(
          recipient,
          employees,
          recipientIndex,
        )}
      </p>

      <p className="truncate text-[10px] font-semibold">
        {fieldDisplayName(field)}
      </p>

      {selected && (
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
      )}
    </div>
  );
}

function PlacementPage({
  pdf,
  pageNumber,
  zoom,
  pageFields,
  recipients,
  employees,
  selectedRecipient,
  activeFieldType,
  selectedField,
  onPlace,
  onSelectField,
  onChangeField,
}) {
  const canvasRef = useRef(null);
  const pageRef = useRef(null);

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
          scale: 1.05 * zoom,
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
    pageNumber,
    pdf,
    zoom,
  ]);

  const place = (event) => {
    if (
      !viewportSize
      || selectedRecipient < 0
      || !pageRef.current
    ) {
      return;
    }

    const rect = pageRef.current
      .getBoundingClientRect();

    const metadata = fieldMetadata(
      activeFieldType,
    );

    const x = clamp(
      (
        (event.clientX - rect.left)
        / rect.width
      ) - (metadata.width / 2),
      0,
      1 - metadata.width,
    );

    const y = clamp(
      (
        (event.clientY - rect.top)
        / rect.height
      ) - (metadata.height / 2),
      0,
      1 - metadata.height,
    );

    onPlace(
      selectedRecipient,
      newField(
        activeFieldType,
        pageNumber,
        x,
        y,
      ),
    );
  };

  return (
    <div
      ref={pageRef}
      role="button"
      tabIndex={0}
      aria-label={`Place ${activeFieldType} field on PDF page ${pageNumber}`}
      className="relative mx-auto cursor-crosshair bg-white shadow-lg outline-none ring-blue-500 focus:ring-2"
      style={viewportSize || undefined}
      onClick={place}
      onKeyDown={() => {}}
    >
      <canvas
        ref={canvasRef}
        className="block"
      />

      {viewportSize && pageFields.map(({
        recipientIndex,
        fieldIndex,
        field,
      }) => (
        <FieldBox
          key={`${recipientIndex}-${fieldIndex}-${field.field_type}`}
          field={field}
          fieldIndex={fieldIndex}
          recipientIndex={recipientIndex}
          recipient={recipients[recipientIndex]}
          employees={employees}
          selected={
            selectedField?.recipientIndex
              === recipientIndex
            && selectedField?.fieldIndex
              === fieldIndex
          }
          pageRef={pageRef}
          onSelect={onSelectField}
          onChange={onChangeField}
        />
      ))}
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

  const [
    selectedRecipientIndex,
    setSelectedRecipient,
  ] = useState(0);

  const [
    activeFieldType,
    setActiveFieldType,
  ] = useState('signature');

  const [
    selectedField,
    setSelectedField,
  ] = useState(null);

  const [currentPage, setCurrentPage] = useState(1);
  const [zoom, setZoom] = useState(1);

  const pdf = (
    pdfState.documentId === documentId
      ? pdfState.pdf
      : null
  );

  const error = (
    pdfState.documentId === documentId
      ? pdfState.error
      : ''
  );

  const selectedRecipient = Math.min(
    selectedRecipientIndex,
    Math.max(0, recipients.length - 1),
  );

  useEffect(() => {
    let active = true;
    let loadingTask;

    documentApi.content(documentId)
      .then(async (blob) => {
        const pdfData = new Uint8Array(
          await blob.arrayBuffer(),
        );

        if (!active) return;

        loadingTask = getDocument({
          data: pdfData,
          isEvalSupported: false,
          enableScripting: false,
        });

        loadingTask.promise
          .then((loaded) => {
            if (!active) return;

            setCurrentPage(1);
            setSelectedField(null);

            setPdfState({
              documentId,
              pdf: loaded,
              error: '',
            });
          })
          .catch(() => {
            if (!active) return;

            setPdfState({
              documentId,
              pdf: null,
              error: (
                'Unable to render this PDF '
                + 'for field placement.'
              ),
            });
          });
      })
      .catch(() => {
        if (!active) return;

        setPdfState({
          documentId,
          pdf: null,
          error: (
            'Unable to load the PDF '
            + 'for field placement.'
          ),
        });
      });

    return () => {
      active = false;
      loadingTask?.destroy?.();
    };
  }, [documentId]);

  const pageFields = useMemo(() => {
    const values = [];

    recipients.forEach((
      recipient,
      recipientIndex,
    ) => {
      (recipient.fields || []).forEach((
        field,
        fieldIndex,
      ) => {
        values.push({
          recipientIndex,
          fieldIndex,
          field,
        });
      });
    });

    return values;
  }, [recipients]);

  const selectedFields = (
    recipients[selectedRecipient]?.fields || []
  );

  const selectedFieldData = (
    selectedField
      ? recipients[
        selectedField.recipientIndex
      ]?.fields?.[
        selectedField.fieldIndex
      ]
      : null
  );

  const selectRecipient = (index) => {
    setSelectedRecipient(index);
    setSelectedField(null);
  };

  const selectField = (
    recipientIndex,
    fieldIndex,
  ) => {
    setSelectedRecipient(recipientIndex);

    setSelectedField({
      recipientIndex,
      fieldIndex,
    });
  };

  const placeField = (
    recipientIndex,
    field,
  ) => {
    const current = (
      recipients[recipientIndex]?.fields || []
    );

    onFieldsChange(
      recipientIndex,
      [
        ...current,
        field,
      ],
    );

    setSelectedField({
      recipientIndex,
      fieldIndex: current.length,
    });

    if (
      field.field_type === 'signature'
      && !current.some(
        (item) => item.field_type === 'date',
      )
    ) {
      setActiveFieldType('date');
    }
  };

  const updateField = (
    recipientIndex,
    fieldIndex,
    changes,
  ) => {
    const current = (
      recipients[recipientIndex]?.fields || []
    );

    onFieldsChange(
      recipientIndex,
      current.map((field, index) => (
        index === fieldIndex
          ? {
            ...field,
            ...changes,
          }
          : field
      )),
    );
  };

  const deleteField = (
    recipientIndex,
    fieldIndex,
  ) => {
    const current = (
      recipients[recipientIndex]?.fields || []
    );

    onFieldsChange(
      recipientIndex,
      current.filter((
        _,
        index,
      ) => index !== fieldIndex),
    );

    setSelectedField(null);
  };

  const clearSelectedSigner = () => {
    onFieldsChange(
      selectedRecipient,
      [],
    );

    setSelectedField(null);
  };

  const selectedComplete = (
    ['signature', 'date'].every((type) => (
      selectedFields.some(
        (field) => field.field_type === type,
      )
    ))
  );

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-slate-100">
      <div className="border-b border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-semibold text-slate-950">
              Prepare signing fields
            </p>

            <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">
              Choose a signatory and field type, then click the
              original PDF. Select a placed field to move, resize,
              configure or delete it. Signature and date remain
              server-controlled during signing.
            </p>
          </div>

          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={clearSelectedSigner}
          >
            <RotateCcw size={14} />
            Clear selected signer
          </Button>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {recipients.map((
            recipient,
            index,
          ) => {
            const fields = recipient.fields || [];

            const complete = (
              ['signature', 'date'].every(
                (type) => fields.some(
                  (field) => (
                    field.field_type === type
                  ),
                ),
              )
            );

            return (
              <button
                key={`${recipient.employee_id || 'recipient'}-${index}`}
                type="button"
                onClick={() => selectRecipient(index)}
                className={`rounded-lg border px-3 py-2 text-left text-xs ${
                  index === selectedRecipient
                    ? 'border-blue-500 bg-blue-50 text-blue-950'
                    : 'border-slate-200 bg-white text-slate-700'
                }`}
              >
                <span className="block font-semibold">
                  {signerName(
                    recipient,
                    employees,
                    index,
                  )}
                </span>

                <span className="mt-0.5 block text-[10px]">
                  {complete
                    ? `${fields.length} field${fields.length === 1 ? '' : 's'} · ready`
                    : `${fields.length} field${fields.length === 1 ? '' : 's'} · signature/date required`}
                </span>
              </button>
            );
          })}
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {FIELD_TYPES.map((metadata) => {
            const active = (
              activeFieldType === metadata.type
            );

            return (
              <button
                key={metadata.type}
                type="button"
                onClick={() => (
                  setActiveFieldType(metadata.type)
                )}
                className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold ${
                  active
                    ? 'border-blue-600 bg-blue-600 text-white'
                    : 'border-slate-200 bg-white text-slate-700'
                }`}
              >
                {metadata.type === 'signature' && (
                  <FileSignature size={14} />
                )}

                {metadata.type === 'date' && (
                  <CalendarDays size={14} />
                )}

                {metadata.label}
              </button>
            );
          })}
        </div>
      </div>

      {!pdf ? (
        <div className="grid min-h-96 place-items-center p-8 text-sm text-slate-500">
          Preparing PDF field editor…
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

            <div className="flex items-center gap-2">
              <button
                type="button"
                aria-label="Zoom out"
                disabled={zoom <= MIN_ZOOM}
                onClick={() => setZoom(
                  (value) => rounded(clamp(
                    value - 0.1,
                    MIN_ZOOM,
                    MAX_ZOOM,
                  )),
                )}
                className="rounded-md border border-slate-200 p-2 text-slate-600 disabled:opacity-40"
              >
                <ZoomOut size={15} />
              </button>

              <span className="min-w-12 text-center text-xs font-semibold text-slate-700">
                {Math.round(zoom * 100)}%
              </span>

              <button
                type="button"
                aria-label="Zoom in"
                disabled={zoom >= MAX_ZOOM}
                onClick={() => setZoom(
                  (value) => rounded(clamp(
                    value + 0.1,
                    MIN_ZOOM,
                    MAX_ZOOM,
                  )),
                )}
                className="rounded-md border border-slate-200 p-2 text-slate-600 disabled:opacity-40"
              >
                <ZoomIn size={15} />
              </button>
            </div>
          </div>

          <div className="grid min-h-[680px] lg:grid-cols-[112px_minmax(0,1fr)_270px]">
            <aside className="max-h-[760px] space-y-2 overflow-auto border-r border-slate-200 bg-slate-50 p-2">
              {Array.from(
                {
                  length: pdf.numPages,
                },
                (_, index) => index + 1,
              ).map((pageNumber) => (
                <PageThumbnail
                  key={pageNumber}
                  pdf={pdf}
                  pageNumber={pageNumber}
                  active={
                    pageNumber === currentPage
                  }
                  onSelect={(page) => {
                    setCurrentPage(page);
                    setSelectedField(null);
                  }}
                />
              ))}
            </aside>

            <main className="max-h-[760px] overflow-auto bg-slate-200/70 p-5">
              <PlacementPage
                pdf={pdf}
                pageNumber={currentPage}
                zoom={zoom}
                pageFields={pageFields.filter(
                  ({ field }) => (
                    field.page_number
                    === currentPage
                  ),
                )}
                recipients={recipients}
                employees={employees}
                selectedRecipient={
                  selectedRecipient
                }
                activeFieldType={
                  activeFieldType
                }
                selectedField={
                  selectedField
                }
                onPlace={placeField}
                onSelectField={(
                  recipientIndex,
                  fieldIndex,
                ) => {
                  selectField(
                    recipientIndex,
                    fieldIndex,
                  );
                }}
                onChangeField={updateField}
              />
            </main>

            <aside className="max-h-[760px] overflow-auto border-l border-slate-200 bg-white p-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
                  Field properties
                </p>

                <p className="mt-1 text-sm font-semibold text-slate-950">
                  {selectedFieldData
                    ? fieldDisplayName(
                      selectedFieldData,
                    )
                    : 'Select a field'}
                </p>
              </div>

              {!selectedFieldData ? (
                <p className="mt-4 text-xs leading-5 text-slate-500">
                  Click a placed field to edit its label,
                  requirement, placeholder or prefill source.
                </p>
              ) : (
                <div className="mt-4 space-y-4">
                  <label className="block space-y-1">
                    <span className="text-xs font-medium text-slate-700">
                      Label
                    </span>

                    <input
                      aria-label="Field label"
                      value={
                        selectedFieldData.label || ''
                      }
                      maxLength={160}
                      onChange={(event) => (
                        updateField(
                          selectedField.recipientIndex,
                          selectedField.fieldIndex,
                          {
                            label: (
                              event.target.value
                            ),
                          },
                        )
                      )}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
                    />
                  </label>

                  <label className="flex items-center gap-2 text-xs font-medium text-slate-700">
                    <input
                      type="checkbox"
                      aria-label="Field required"
                      checked={
                        selectedFieldData.required
                        !== false
                      }
                      disabled={[
                        'signature',
                        'date',
                      ].includes(
                        selectedFieldData.field_type,
                      )}
                      onChange={(event) => (
                        updateField(
                          selectedField.recipientIndex,
                          selectedField.fieldIndex,
                          {
                            required: (
                              event.target.checked
                            ),
                          },
                        )
                      )}
                    />

                    Required field
                  </label>

                  {[
                    'text',
                    'initials',
                  ].includes(
                    selectedFieldData.field_type,
                  ) && (
                    <>
                      <label className="block space-y-1">
                        <span className="text-xs font-medium text-slate-700">
                          Placeholder
                        </span>

                        <input
                          aria-label="Field placeholder"
                          value={
                            selectedFieldData
                              .placeholder || ''
                          }
                          maxLength={240}
                          onChange={(event) => (
                            updateField(
                              selectedField
                                .recipientIndex,
                              selectedField
                                .fieldIndex,
                              {
                                placeholder: (
                                  event.target.value
                                  || null
                                ),
                              },
                            )
                          )}
                          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
                          placeholder="Instruction shown to the signatory"
                        />
                      </label>

                      <label className="block space-y-1">
                        <span className="text-xs font-medium text-slate-700">
                          HR prefill
                        </span>

                        <select
                          aria-label="Prefill source"
                          value={
                            selectedFieldData
                              .prefill_key || ''
                          }
                          onChange={(event) => (
                            updateField(
                              selectedField
                                .recipientIndex,
                              selectedField
                                .fieldIndex,
                              {
                                prefill_key: (
                                  event.target.value
                                  || null
                                ),
                              },
                            )
                          )}
                          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
                        >
                          {PREFILL_OPTIONS.map(
                            (option) => (
                              <option
                                key={option.value}
                                value={option.value}
                              >
                                {option.label}
                              </option>
                            ),
                          )}
                        </select>
                      </label>
                    </>
                  )}

                  {[
                    'signature',
                    'date',
                    'name',
                  ].includes(
                    selectedFieldData.field_type,
                  ) && (
                    <p className="rounded-lg bg-slate-50 p-3 text-[11px] leading-5 text-slate-600">
                      This value is generated from authoritative
                      Kinetic identity or server time during
                      signing and cannot be overridden by the
                      signatory.
                    </p>
                  )}

                  <button
                    type="button"
                    aria-label="Delete selected field"
                    onClick={() => deleteField(
                      selectedField.recipientIndex,
                      selectedField.fieldIndex,
                    )}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-semibold text-red-700 hover:bg-red-100"
                  >
                    <Trash2 size={14} />
                    Delete field
                  </button>
                </div>
              )}

              <div className="mt-6 border-t border-slate-200 pt-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
                    Signer fields
                  </p>

                  <span className={`text-[10px] font-semibold ${
                    selectedComplete
                      ? 'text-emerald-700'
                      : 'text-amber-700'
                  }`}
                  >
                    {selectedComplete
                      ? 'Ready'
                      : 'Needs signature + date'}
                  </span>
                </div>

                <div className="mt-2 space-y-2">
                  {selectedFields.length === 0 ? (
                    <p className="text-xs text-slate-500">
                      No fields placed yet.
                    </p>
                  ) : (
                    selectedFields.map((
                      field,
                      fieldIndex,
                    ) => (
                      <button
                        key={`${fieldIndex}-${field.field_type}`}
                        type="button"
                        aria-label={`Select ${fieldDisplayName(field)} field ${fieldIndex + 1}`}
                        onClick={() => {
                          setCurrentPage(
                            field.page_number,
                          );

                          selectField(
                            selectedRecipient,
                            fieldIndex,
                          );
                        }}
                        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-left text-xs hover:border-blue-300 hover:bg-blue-50"
                      >
                        <span className="block font-semibold text-slate-800">
                          {fieldDisplayName(field)}
                        </span>

                        <span className="mt-0.5 block text-[10px] text-slate-500">
                          Page {field.page_number}
                          {' · '}
                          {field.required
                            ? 'Required'
                            : 'Optional'}
                        </span>
                      </button>
                    ))
                  )}
                </div>
              </div>
            </aside>
          </div>
        </>
      )}
    </section>
  );
}
