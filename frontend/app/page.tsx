import VisaRefShell from "@/components/visaref/visaref-shell";
import PinGate from "@/components/visaref/pin-gate";

export default function Home() {
  return (
    <div className="h-dvh">
      <PinGate>
        <VisaRefShell />
      </PinGate>
    </div>
  );
}
