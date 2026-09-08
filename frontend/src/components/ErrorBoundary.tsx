import { Component, type ReactNode, type ErrorInfo } from 'react';

interface Props {
  children: ReactNode;
  fallback?: (error: Error) => ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * ErrorBoundary — catches render-time JS exceptions and shows an inline
 * error panel instead of a blank page. rules.md §2: the app must never
 * produce a completely blank screen on error.
 */
export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary] Caught render error:', error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (error) {
      if (this.props.fallback) return this.props.fallback(error);
      return (
        <div style={{
          position: 'fixed', inset: 0, display: 'flex', alignItems: 'center',
          justifyContent: 'center', background: 'var(--panel-1, #0d1117)',
          zIndex: 9999,
        }}>
          <div style={{
            maxWidth: 560, padding: '32px', borderRadius: '8px',
            background: 'rgba(193,81,47,0.12)', border: '1px solid #c1512f',
            fontFamily: 'monospace', color: '#e8d5b7',
          }}>
            <div style={{ fontSize: '13px', fontWeight: 700, color: '#e07a5f', marginBottom: '12px' }}>
              ⚠ Render Error — application state is inconsistent
            </div>
            <div style={{ fontSize: '11px', color: '#e8d5b7', marginBottom: '16px' }}>
              {error.message}
            </div>
            <button
              onClick={() => this.setState({ error: null })}
              style={{
                padding: '6px 16px', fontSize: '11px', cursor: 'pointer',
                background: 'rgba(193,81,47,0.3)', border: '1px solid #c1512f',
                borderRadius: '4px', color: '#e8d5b7',
              }}
            >
              Dismiss and retry
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
