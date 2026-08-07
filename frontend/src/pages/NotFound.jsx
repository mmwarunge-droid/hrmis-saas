import { ArrowLeft, Home, SearchX } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';

export default function NotFound() {
  const navigate = useNavigate();
  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 p-6">
      <Card className="w-full max-w-xl py-10 text-center">
        <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl border border-blue-100 bg-blue-50 text-blue-700">
          <SearchX size={25} />
        </span>
        <p className="mt-5 text-xs font-bold uppercase tracking-[0.16em] text-blue-700">404 · Not found</p>
        <h1 className="mt-2 text-2xl font-bold tracking-[-0.025em] text-slate-950">This page is not available</h1>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-600">
          The address may be incorrect, or your role may no longer have access to this destination.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Button type="button" variant="secondary" onClick={() => navigate(-1)}>
            <ArrowLeft size={16} /> Go back
          </Button>
          <Button as={Link} to="/dashboard"><Home size={16} /> Open home</Button>
        </div>
      </Card>
    </main>
  );
}
