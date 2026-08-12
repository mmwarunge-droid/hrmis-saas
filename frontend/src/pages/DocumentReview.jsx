import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import { documentApi } from '../api/documentApi.js';
import Alert from '../components/ui/Alert.jsx';
import Card from '../components/ui/Card.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';

export default function DocumentReview() {
  const { documentId } = useParams();
  const [document, setDocument] = useState(null);
  const [documentUrl, setDocumentUrl] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    let objectUrl = '';
    Promise.all([
      documentApi.get(documentId),
      documentApi.content(documentId),
    ])
      .then(([metadata, content]) => {
        if (!active) return;
        setDocument(metadata.data);
        objectUrl = URL.createObjectURL(content.data);
        setDocumentUrl(objectUrl);
      })
      .catch((err) => setError(err.error?.message || 'Unable to open document.'));
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [documentId]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Document review"
        title={document?.title || 'Review document'}
        description="Secure in-browser review. Close this tab when you are finished and return to Kinetic to complete the required action."
      />
      {error && <Alert type="error">{error}</Alert>}
      <Card className="overflow-hidden p-0">
        {documentUrl ? (
          <iframe title={document?.title || 'Document'} src={documentUrl} className="h-[78vh] w-full" />
        ) : (
          <div className="grid h-[78vh] place-items-center text-sm text-slate-500">Preparing document viewer…</div>
        )}
      </Card>
    </div>
  );
}
