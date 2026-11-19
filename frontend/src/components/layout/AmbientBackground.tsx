"use client";

// The ambient colour blobs were removed in the design pass (flat background).
// The component and its `parallax` prop stay so page.tsx and useMouseParallax
// are untouched; it now renders nothing.
export default function AmbientBackground(props: { parallax: { x: number; y: number } }) {
  void props;
  return null;
}
