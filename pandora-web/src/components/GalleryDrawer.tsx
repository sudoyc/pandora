// pandora-web/src/components/GalleryDrawer.tsx
import * as Dialog from '@radix-ui/react-dialog';
import * as Tabs from '@radix-ui/react-tabs';

export const GalleryDrawer = ({ open, onOpenChange, gid, token }: any) => {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)' }} />
        <Dialog.Content style={{ position: 'fixed', right: 0, top: 0, bottom: 0, width: 'var(--drawer-width)', background: 'var(--bg-sidebar)', padding: '20px' }}>
          <Tabs.Root defaultValue="info">
            <Tabs.List style={{ display: 'flex', gap: '20px', borderBottom: '1px solid #444' }}>
              <Tabs.Trigger value="info">Info</Tabs.Trigger>
              <Tabs.Trigger value="previews">Previews</Tabs.Trigger>
              <Tabs.Trigger value="comments">Comments</Tabs.Trigger>
            </Tabs.List>
            <Tabs.Content value="info">
               {/* Fetch and show detail here */}
               <div>GID: {gid} / Token: {token}</div>
               <Dialog.Close>Close</Dialog.Close>
            </Tabs.Content>
          </Tabs.Root>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};
