export function formatDate(value) {
  if (!value) return '-';
  return new Intl.DateTimeFormat('en-KE', { dateStyle: 'medium' }).format(new Date(value));
}
