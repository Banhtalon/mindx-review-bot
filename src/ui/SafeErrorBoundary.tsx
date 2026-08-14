import { Component, type ReactNode } from "react";

type SafeErrorBoundaryProps = {
  readonly children: ReactNode;
};

type SafeErrorBoundaryState = {
  readonly hasError: boolean;
};

export class SafeErrorBoundary extends Component<SafeErrorBoundaryProps, SafeErrorBoundaryState> {
  state: SafeErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): SafeErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(): void {
    // Intentionally avoid logging exception details that may contain sensitive data.
  }

  render() {
    if (this.state.hasError) {
      return <p role="alert">The application could not continue safely. Reload the page to try again.</p>;
    }

    return this.props.children;
  }
}
