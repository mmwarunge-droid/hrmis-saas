import { useState } from 'react';

import Form from '../forms/Form.jsx';
import Button from '../ui/Button.jsx';
import Input from '../ui/Input.jsx';
import Select from '../ui/Select.jsx';

export default function DocumentUpload({
  onSubmit,
  loading = false,
  isSuperAdmin = false,
  tenants = [],
}) {
  const [form, setForm] = useState({
    tenant_id: '',
    title: '',
    document_type: 'contract',
    access_level: 'hr_only',
    expiry_date: '',
  });
  const [file, setFile] = useState(null);

  const submit = (event) => {
    event.preventDefault();

    const data = new FormData();

    Object.entries(form).forEach(([key, value]) => {
      if (value) data.append(key, value);
    });

    if (file) data.append('file', file);

    return onSubmit(data);
  };

  return (
    <Form
      draft={{
        key: 'document.upload',
        title: 'Upload document',
        data: form,
        onRestore: setForm,
      }}
      onSubmit={submit}
      className="space-y-4"
    >
      {isSuperAdmin && (
        <Select
          label="Organization"
          value={form.tenant_id}
          onChange={(event) => setForm({
            ...form,
            tenant_id: event.target.value,
          })}
          required
          disabled={tenants.length === 0}
        >
          <option value="">
            {tenants.length
              ? 'Select organization'
              : 'No organizations available'}
          </option>

          {tenants.map((tenant) => (
            <option key={tenant.id} value={tenant.id}>
              {tenant.name}
            </option>
          ))}
        </Select>
      )}

      <Input
        label="Title"
        value={form.title}
        onChange={(event) => setForm({
          ...form,
          title: event.target.value,
        })}
        required
      />

      <Select
        label="Document type"
        value={form.document_type}
        onChange={(event) => setForm({
          ...form,
          document_type: event.target.value,
        })}
      >
        <option value="contract">Contract</option>
        <option value="policy">Policy</option>
        <option value="tax">Tax</option>
        <option value="certification">Certification</option>
        <option value="id">ID</option>
        <option value="other">Other</option>
      </Select>

      <Input
        label="Expiry date"
        type="date"
        value={form.expiry_date}
        onChange={(event) => setForm({
          ...form,
          expiry_date: event.target.value,
        })}
      />

      <Input
        label="Choose file"
        type="file"
        accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg,.txt"
        hint="PDF, Word, Excel, PNG, JPEG, or text. Uploaded files are initially visible to HR only."
        onChange={(event) => setFile(event.target.files[0])}
        required
      />

      <Button type="submit" disabled={loading}>
        {loading ? 'Uploading...' : 'Upload document'}
      </Button>
    </Form>
  );
}