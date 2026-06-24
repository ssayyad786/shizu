interface Props {
  tagline?: string;
  size?: "sm" | "md";
}

export default function BrandMark({ tagline = "Market Monitor", size = "md" }: Props) {
  return (
    <div className={`brand-mark brand-mark-${size}`}>
      <img src="/favicon.svg" alt="" className="brand-logo" width={40} height={40} aria-hidden />
      <div className="brand-text">
        <span className="brand-name">Shizu</span>
        {tagline ? <span className="brand-tagline">{tagline}</span> : null}
      </div>
    </div>
  );
}
