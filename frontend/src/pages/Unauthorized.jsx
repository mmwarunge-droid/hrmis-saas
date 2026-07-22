import Card from '../components/ui/Card.jsx';

export default function Unauthorized() {
  return <main className="grid min-h-screen place-items-center bg-slate-50 p-4"><Card><h1 className="text-2xl font-bold">Unauthorized</h1><p className="mt-2 text-slate-600">You do not have access to this page.</p></Card></main>;
}
