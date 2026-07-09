import { EditableCardTypes } from "../contracts/integrationContracts.js";

export const demoState = {
  pharmacy: {
    id: "demo-pharmacy",
    name: "Your pharmacy",
    owner: "Owner",
    branch: "Main",
    location: "Kenya",
    catalogLoaded: false
  },
  sync: {
    online: true,
    cloud: "placeholder",
    lastSync: "Not synced yet",
    pending: 0
  },
  today: {
    sales: 0,
    cash: 0,
    mpesa: 0,
    credit: 0
  },
  cards: [],
  feed: [
    {
      id: "feed-welcome",
      type: "system",
      text: "Welcome to MS2.0 setup. Let's set up your pharmacy quickly.",
      time: "Now"
    },
    {
      id: "feed-principle",
      type: "system",
      text: "Open, speak or type, review the card, confirm. Three steps or less.",
      time: "Now"
    }
  ],
  cardTypes: EditableCardTypes
};

export function nowLabel() {
  return new Intl.DateTimeFormat("en-KE", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(new Date());
}
