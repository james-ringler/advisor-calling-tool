import type { DiscardDuration } from '../types'

interface Props {
  leadName: string
  onConfirm: (duration: DiscardDuration) => void
  onCancel: () => void
}

const OPTIONS: { value: DiscardDuration; label: string; description: string }[] = [
  { value: 'today', label: 'Discard for today', description: 'Will reappear tomorrow' },
  { value: '30days', label: 'Discard for 30 days', description: 'Will reappear in a month' },
  { value: 'forever', label: 'Discard forever', description: 'Will never appear again' },
]

export default function DiscardModal({ leadName, onConfirm, onCancel }: Props) {
  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h2 className="modal-title">Discard {leadName}?</h2>
        <p className="modal-subtitle">How long should this contact be hidden?</p>
        <div className="modal-options">
          {OPTIONS.map((opt) => (
            <button
              key={opt.value}
              className={`modal-option ${opt.value === 'forever' ? 'modal-option--danger' : ''}`}
              onClick={() => onConfirm(opt.value)}
            >
              <span className="modal-option-label">{opt.label}</span>
              <span className="modal-option-desc">{opt.description}</span>
            </button>
          ))}
        </div>
        <button className="modal-cancel" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  )
}
