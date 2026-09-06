export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'

export type ButtonProps = {
    children: React.ReactNode
    variant: ButtonVariant
    onClick?: () => void
    isDisabled?: boolean
    popoverTarget?: string
    popoverTargetAction?: 'show' | 'hide' | 'toggle'
    title?: string
    ariaLabel?: string
}

const BUTTON_CLASS_NAME: Record<ButtonVariant, string> = {
    primary:
        'rounded-lg bg-accent px-6 py-3 text-sm font-semibold text-canvas transition-colors hover:bg-accent-soft disabled:cursor-not-allowed disabled:bg-surface-raised disabled:text-ink-faint',
    secondary:
        'rounded-lg border border-line-strong bg-surface px-4 py-2.5 text-sm font-medium text-ink transition-colors hover:border-ink-faint hover:bg-surface-raised',
    ghost: 'rounded-lg px-3 py-2 text-sm font-medium text-ink-muted transition-colors hover:bg-white/5 hover:text-ink',
    danger: 'rounded-lg border border-peach/30 bg-transparent px-4 py-2.5 text-sm font-medium text-peach transition-colors hover:bg-peach/10',
}

const Button = ({
    children,
    variant,
    onClick,
    isDisabled,
    popoverTarget,
    popoverTargetAction,
    title,
    ariaLabel,
}: ButtonProps) => {
    return (
        <button
            type="button"
            className={BUTTON_CLASS_NAME[variant]}
            onClick={onClick}
            disabled={isDisabled}
            popoverTarget={popoverTarget}
            popoverTargetAction={popoverTargetAction}
            title={title}
            aria-label={ariaLabel}
        >
            {children}
        </button>
    )
}

export default Button
