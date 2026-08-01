export function initials(name = '') {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || 'KP';
}

export default function Avatar({ name, size = 'md', className = '', src, alt = '' }) {
  const sizes = {
    xs: 'h-7 w-7 text-[10px]',
    sm: 'h-8 w-8 text-[11px]',
    md: 'h-10 w-10 text-xs',
    lg: 'h-14 w-14 text-base',
    xl: 'h-20 w-20 text-xl',
    '2xl': 'h-24 w-24 text-2xl',
  };

  if (src) {
    return <img src={src} alt={alt || name || ''} className={`shrink-0 rounded-full object-cover ring-2 ring-white ${sizes[size] || sizes.md} ${className}`} />;
  }

  return (
    <span className={`inline-flex shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-blue-800 font-bold text-white ring-2 ring-white ${sizes[size] || sizes.md} ${className}`}>
      {initials(name)}
    </span>
  );
}
