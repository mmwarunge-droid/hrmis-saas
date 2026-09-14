import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import { documentApi } from '../api/documentApi.js';
import Alert from '../components/ui/Alert.jsx';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';
import EmptyState from '../components/ui/EmptyState.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';

export default function DocumentReview() {
  const { documentId } = useParams();
  const [document, setDocument] = useState(null);
  const [documentUrl, setDocumentUrl] = useState('');
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    let objectUrl = '';

    Promise.all([
      documentApi.get(documentId),
      documentApi.content(documentId),
    ])
      .then(([metadata, content]) => {
        if (!active) return;

        setError('');
        setDocument(metadata.data);
        objectUrl = URL.createObjectURL(content.data);
        setDocumentUrl(objectUrl);
      })
      .catch((err) => {
        if (active) {
          setError(
            err.error?.message
            || 'We couldn’t open this document. Try again or download a copy.',
          );
        }
      });

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [documentId, attempt]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Document review"
        title={document?.title || 'Review document'}
        description="Secure in-browser review. Close this tab when you are finished and return to Kinetic to complete the required action."
        actions={(
          <Button
            as="a"
            href={documentApi.downloadUrl(documentId)}
            variant="secondary"
          >
            Download document
          </Button>
        )}
      />

      {error && <Alert type="error">{error}</Alert>}

      <Card className="overflow-hidden p-0">
        {error ? (
          <EmptyState
            title="Document preview unavailable"
            description="Try loading the preview again. You can also download the document to review it on your device."
            action={(
              <Button
                type="button"
                onClick={() => {
                  setError('');
                  setDocumentUrl('');
                  setAttempt((value) => value + 1);
                }}
              >
                Try again
              </Button>
            )}
          />
        ) : documentUrl ? (
          <iframe
            title={document?.title || 'Document'}
            src={documentUrl}
            className="h-[78vh] w-full"
          />
        ) : (
          <div
            role="status"
            className="grid h-[78vh] place-items-center text-sm text-slate-500"
          >
            Preparing document viewer…
          </div>
        )}
      </Card>
    </div>
  );
}