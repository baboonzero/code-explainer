type Props = {
  label: string;
  value: string;
};

export function KpiCard({ label, value }: Props) {
  return (
    <section>
      <strong>{label}</strong>
      <span>{value}</span>
    </section>
  );
}
