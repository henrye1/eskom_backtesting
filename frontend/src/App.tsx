import Sidebar from './components/layout/Sidebar';
import Dashboard from './pages/Dashboard';

export default function App() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-gray-50">
        <Dashboard />
      </main>
    </div>
  );
}
