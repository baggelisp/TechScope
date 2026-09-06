export type ButtonRowProps = {
    children: React.ReactNode
}

/**
 * A row of actions that becomes a stack on a phone.
 *
 * The buttons themselves stay unaware of it: how several controls sit beside each other is the
 * arrangement's business, and only the thing holding them can see the arrangement.
 */
const ButtonRow = ({ children }: ButtonRowProps) => {
    return (
        <div className="flex w-full flex-col gap-2 *:w-full sm:w-auto sm:flex-row sm:items-center sm:*:w-auto">
            {children}
        </div>
    )
}

export default ButtonRow
