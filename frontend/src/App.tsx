import { Routes, Route } from 'react-router-dom';
import GuestLanding from './components/GuestLanding';
import Listener from './components/Listener';
import OperatorConsole from './components/OperatorConsole';

export default function App() {
  return (
    <div className="relative min-h-screen overflow-x-hidden bg-sand-base text-body antialiased font-sans">
      <div
        data-testid="app-background"
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(680px_360px_at_50%_0%,var(--color-brand-tint),transparent_70%)]"
      />
      <div className="relative">
        <Routes>
          {/* VIEW 1: GUEST QR LANDING (language picker for scanned pew codes) */}
          <Route path="/" element={<GuestLanding />} />

          {/* VIEW 2: GUEST LISTENER VIEW (transcript + translation, headphone audio) */}
          <Route path="/listen/:roomId/:lang" element={<Listener />} />

          {/* VIEW 3: OPERATOR CONSOLE (operator login + feed control) */}
          <Route path="/operate" element={<OperatorConsole />} />
        </Routes>
      </div>
    </div>
  );
}
