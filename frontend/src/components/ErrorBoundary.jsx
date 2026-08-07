import React from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';
import Button from './ui/Button.jsx';
import KineticLogo from './ui/KineticLogo.jsx';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null, reference: null };
  }

  static getDerivedStateFromError(error) {
    return {
      error,
      reference: `UI-${Date.now().toString(36).toUpperCase()}`,
    };
  }

  componentDidCatch(error, info) {
    console.error('Kinetic UI failure', {
      error,
      componentStack: info.componentStack,
      reference: this.state.reference,
    });
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <main className="grid min-h-screen place-items-center bg-slate-50 p-6">
        <section className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-7 text-center shadow-xl">
          <KineticLogo className="mx-auto" />
          <span className="mx-auto mt-8 grid h-12 w-12 place-items-center rounded-xl border border-red-100 bg-red-50 text-red-700">
            <AlertTriangle size={22} />
          </span>
          <h1 className="mt-4 text-2xl font-bold tracking-[-0.025em] text-slate-950">
            This workspace could not finish loading
          </h1>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-600">
            Reload the page to recover. Provide the reference below to support if the problem continues.
          </p>
          <p className="mt-4 font-mono text-xs font-semibold text-slate-500">
            Reference: {this.state.reference}
          </p>
          <Button
            type="button"
            className="mt-6"
            onClick={() => window.location.reload()}
          >
            <RotateCcw size={16} /> Reload workspace
          </Button>
        </section>
      </main>
    );
  }
}
