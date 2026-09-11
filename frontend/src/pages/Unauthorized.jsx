import { ArrowLeft, Home, ShieldAlert } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';

import Button from '../components/ui/Button.jsx';
import Card from '../components/ui/Card.jsx';

export default function Unauthorized() {
  const navigate = useNavigate();

  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 p-6">
      <Card className="w-full max-w-xl py-10 text-center">
        <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl border border-amber-100 bg-amber-50 text-amber-700">
          <ShieldAlert size={25} />
        </span>

        <p className="mt-5 text-xs font-bold uppercase tracking-[0.16em] text-amber-700">
          403 · Access denied
        </p>

        <h1 className="mt-2 text-2xl font-bold tracking-[-0.025em] text-slate-950">
          You do not have access to this page
        </h1>

        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-600">
          Your current role does not have permission to open this destination.
          If you believe you should have access, contact your administrator.
        </p>

        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Button
            type="button"
            variant="secondary"
            onClick={() => navigate(-1)}
          >
            <ArrowLeft size={16} />
            Go back
          </Button>

          <Button as={Link} to="/dashboard">
            <Home size={16} />
            Open home
          </Button>
        </div>
      </Card>
    </main>
  );
}
