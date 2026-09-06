export type CardTone = 'plain' | 'warning' | 'danger'

export type CardProps = {
    children: React.ReactNode
    tone: CardTone
}

const CARD_CLASS_NAME: Record<CardTone, string> = {
    plain: 'rounded-xl border border-line bg-surface p-3 sm:p-6',
    warning: 'rounded-xl border border-peach/25 bg-peach/5 p-3 sm:p-6',
    danger: 'rounded-xl border border-peach/30 bg-peach/10 p-3 sm:p-6',
}

const Card = ({ children, tone }: CardProps) => {
    return <div className={CARD_CLASS_NAME[tone]}>{children}</div>
}

export default Card
