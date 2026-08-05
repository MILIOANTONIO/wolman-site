// Web component del widget ElevenLabs (script esterno, non tipizzato da React) -
// dichiarato qui una volta sola invece di @ts-expect-error sparsi nel JSX.
// React 19 sposta i tipi JSX sotto React.JSX, quindi l'augmentation va sul
// modulo "react", non sul vecchio namespace globale JSX.
import type { DetailedHTMLProps, HTMLAttributes } from "react";

declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "elevenlabs-convai": DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement> & {
        "agent-id"?: string;
        "avatar-image-url"?: string;
        "avatar-orb-color-1"?: string;
        "avatar-orb-color-2"?: string;
        "action-text"?: string;
        variant?: string;
        placement?: string;
        dismissible?: string;
      };
    }
  }
}
