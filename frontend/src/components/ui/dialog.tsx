import * as React from "react"
import * as BaseUI from "@base-ui-components/react"
import { cn } from "@/lib/utils"
import { IconX } from "@tabler/icons-react"

// Base UI exposes Dialog as a namespace: BaseUI.Dialog.Root, .Trigger, etc.
const Dialog = BaseUI.Dialog.Root

const DialogTrigger = BaseUI.Dialog.Trigger

const DialogPortal = BaseUI.Dialog.Portal

const DialogClose = BaseUI.Dialog.Close

const DialogBackdrop = React.forwardRef<HTMLDivElement, React.ComponentPropsWithoutRef<typeof BaseUI.Dialog.Backdrop>>(
  ({ className, ...props }, ref) => (
    <BaseUI.Dialog.Backdrop
      ref={ref}
      className={cn("fixed inset-0 z-50 bg-black/50 backdrop-blur-sm data-[open]:animate-in data-[closed]:animate-out data-[closed]:fade-out-0 data-[open]:fade-in-0", className)}
      {...props}
    />
  )
)
DialogBackdrop.displayName = "DialogBackdrop"

const DialogOverlay = DialogBackdrop

const DialogPopup = React.forwardRef<HTMLDivElement, React.ComponentPropsWithoutRef<typeof BaseUI.Dialog.Popup>>(
  ({ className, ...props }, ref) => (
    <BaseUI.Dialog.Popup
      ref={ref}
      className={cn(
        "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 data-[open]:animate-in data-[closed]:animate-out data-[closed]:fade-out-0 data-[open]:fade-in-0 data-[closed]:zoom-out-95 data-[open]:zoom-in-95 data-[closed]:slide-out-to-left-1/2 data-[closed]:slide-out-to-top-[48%] data-[open]:slide-in-from-left-1/2 data-[open]:slide-in-from-top-[48%] sm:rounded-lg",
        className
      )}
      {...props}
    />
  )
)
DialogPopup.displayName = "DialogPopup"

const DialogContent = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof BaseUI.Dialog.Popup> & { showClose?: boolean }
>(({ className, children, showClose = true, ...props }, ref) => (
  <DialogPortal>
    <DialogBackdrop />
    <DialogPopup ref={ref} className={className} {...props}>
      {children}
      {showClose && (
        <DialogClose className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[open]:bg-accent data-[open]:text-muted-foreground">
          <IconX className="h-4 w-4" />
          <span className="sr-only">Close</span>
        </DialogClose>
      )}
    </DialogPopup>
  </DialogPortal>
))
DialogContent.displayName = "DialogContent"

const DialogHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex flex-col space-y-1.5 text-center sm:text-left", className)} {...props} />
)
DialogHeader.displayName = "DialogHeader"

const DialogFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2", className)} {...props} />
)
DialogFooter.displayName = "DialogFooter"

const DialogTitle = React.forwardRef<HTMLHeadingElement, React.ComponentPropsWithoutRef<typeof BaseUI.Dialog.Title>>(
  ({ className, ...props }, ref) => (
    <BaseUI.Dialog.Title ref={ref} className={cn("text-lg font-semibold leading-none tracking-tight", className)} {...props} />
  )
)
DialogTitle.displayName = "DialogTitle"

const DialogDescription = React.forwardRef<HTMLParagraphElement, React.ComponentPropsWithoutRef<typeof BaseUI.Dialog.Description>>(
  ({ className, ...props }, ref) => (
    <BaseUI.Dialog.Description ref={ref} className={cn("text-sm text-muted-foreground", className)} {...props} />
  )
)
DialogDescription.displayName = "DialogDescription"

export {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogClose,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
  DialogBackdrop,
  DialogPopup,
}
