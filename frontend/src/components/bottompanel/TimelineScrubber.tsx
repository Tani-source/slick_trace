export default function TimelineScrubber() {
  return (
    <div className="flex items-center gap-2 px-4 h-full text-caption text-text-secondary">
      <span className="text-text-disabled">Timeline scrubber — available when AIS playback or drift-sim playback is active</span>
    </div>
  );
}
