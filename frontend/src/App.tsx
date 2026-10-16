import { Routes, Route } from 'react-router-dom';
import GuestLanding from './components/GuestLanding';
import Listener from './components/Listener';
import OperatorConsole from './components/OperatorConsole';

export default function App() {
  return (
    <div className="relative min-h-screen overflow-x-hidden bg-gradient-to-br from-indigo-50 via-white to-violet-100 text-slate-800 antialiased font-sans selection:bg-indigo-100 selection:text-indigo-900">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-32 -left-32 h-96 w-96 rounded-full bg-indigo-300/40 blur-3xl" />
        <div className="absolute top-1/3 -right-32 h-[28rem] w-[28rem] rounded-full bg-violet-300/40 blur-3xl" />
        <div className="absolute -bottom-24 left-1/4 h-80 w-80 rounded-full bg-amber-200/50 blur-3xl" />
      </div>
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
