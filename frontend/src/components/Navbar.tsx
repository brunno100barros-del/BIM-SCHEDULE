import React from 'react';
import { Sun, Moon, Bell, Search } from 'lucide-react';

interface NavbarProps {
  darkMode: boolean;
  onToggleDarkMode: () => void;
  activeProjectName?: string;
}

export const Navbar: React.FC<NavbarProps> = ({ darkMode, onToggleDarkMode, activeProjectName }) => {
  return (
    <header className="h-16 bg-slate-900 border-b border-slate-800 px-6 flex items-center justify-between sticky top-0 z-20">
      <div className="flex items-center space-x-4">
        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 transform -translate-y-1/2" />
          <input
            type="text"
            placeholder="Buscar atividades, EAP, elementos IFC..."
            className="bg-slate-800/70 border border-slate-700/80 rounded-lg pl-9 pr-4 py-1.5 text-xs text-slate-200 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 w-80"
          />
        </div>
      </div>

      <div className="flex items-center space-x-4">
        <button
          onClick={onToggleDarkMode}
          className="p-2 rounded-lg bg-slate-800/80 border border-slate-700 text-slate-300 hover:text-white transition-colors"
          title="Alternar tema"
        >
          {darkMode ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-blue-400" />}
        </button>

        <button className="p-2 rounded-lg bg-slate-800/80 border border-slate-700 text-slate-300 hover:text-white transition-colors relative">
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-blue-500 rounded-full"></span>
        </button>

        <div className="flex items-center space-x-3 pl-3 border-l border-slate-800">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white font-semibold text-xs shadow">
            BR
          </div>
          <div className="hidden md:block text-left">
            <p className="text-xs font-semibold text-slate-200">Brunno Resplandes</p>
            <p className="text-[10px] text-slate-400">Engenheiro Civil / BIM</p>
          </div>
        </div>
      </div>
    </header>
  );
};
