import { MapPin, RotateCcw, Maximize2, PenTool, Camera, ZoomIn, ZoomOut } from 'lucide-react';

const tools = [
  { Icon: ZoomIn, label: 'Zoom in', action: () => {} },
  { Icon: ZoomOut, label: 'Zoom out', action: () => {} },
  { Icon: RotateCcw, label: 'Reset view', action: () => {} },
  { Icon: Maximize2, label: 'Maximize', action: () => {} },
  { Icon: PenTool, label: 'Annotate', action: () => {} },
  { Icon: Camera, label: 'Screenshot', action: () => {} },
];

export default function FloatingToolStack() {
  return (
    <div className="absolute right-4 top-1/2 -translate-y-1/2 flex flex-col gap-3 z-[1000]">
      {tools.map(({ Icon, label, action }) => (
        <button
          key={label}
          type="button"
          title={label}
          aria-label={label}
          onClick={action}
          className="w-10 h-10 rounded-full flex items-center justify-center bg-panel-raised text-text-primary hover:text-accent-teal transition"
        >
          <Icon size={18} />
        </button>
      ))}
    </div>
  );
}
