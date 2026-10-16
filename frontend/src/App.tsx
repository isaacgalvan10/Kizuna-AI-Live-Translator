import { Routes, Route } from 'react-router-dom';
import GuestLanding from './components/GuestLanding';
import Listener from './components/Listener';
import OperatorConsole from './components/OperatorConsole';

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 antialiased font-sans selection:bg-indigo-100 selection:text-indigo-900">
      <Routes>
        {/* VIEW 1: GUEST QR LANDING (language picker for scanned pew codes) */}
        <Route path="/" element={<GuestLanding />} />

        {/* VIEW 2: GUEST LISTENER VIEW (transcript + translation, headphone audio) */}
        <Route path="/listen/:roomId/:lang" element={<Listener />} />

        {/* VIEW 3: OPERATOR CONSOLE (operator login + feed control) */}
        <Route path="/operate" element={<OperatorConsole />} />
      </Routes>
    </div>
  );
}
