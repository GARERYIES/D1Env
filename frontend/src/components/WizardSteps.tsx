export const steps = ['使用方式', '机器人配置', '执行电脑', '部署预览', '运行与结果'];

export function WizardSteps({ current, onSelect, disabled }: { current: number; onSelect: (step: number) => void; disabled: boolean }) {
  return <nav className="wizard-steps" aria-label="部署向导步骤">
    {steps.map((label, index) => <button key={label} type="button" disabled={disabled} aria-current={index === current ? 'step' : undefined} aria-label={`${index + 1} ${label}`} onClick={() => onSelect(index)}>
      <span className="step-number">{String(index + 1).padStart(2, '0')}</span>
      <span>{label}</span>
    </button>)}
  </nav>;
}
