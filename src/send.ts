import { Context, Markup } from "telegraf";
import { InlineKeyboardMarkup, ReplyKeyboardRemove } from "telegraf/types";

const escapeForMessage = (text: string) => {
  return text.replace(
    /(\[[^\][]*]\(http[^()]*\))|[_*[\]()~>#+=|{}.!-]/gi,
    (x, y) => (y ? y : "\\" + x)
  );
};
export type MessageText = {
  type: "text";
  text: string;
  markup: string[];
};
export type MessagePhoto = {
  type: "photo";
  file_id: string;
  markup: string[];
  extra: {
    caption?: string;
  };
};
export type MessageLocation = {
  type: "location";
  lat: number;
  lng: number;
  markup: string[];
};
export type MessageDocument = {
  type: "document";
  file_id: string;
  caption: string;
  markup: string[];
};
export type Message =
  | string
  | MessageText
  | MessagePhoto
  | MessageLocation
  | MessageDocument;

export async function send(ctx: Context, messages: Message[]) {
  for (let message of messages) {
    if (typeof message === "string") {
      await ctx.replyWithMarkdownV2(escapeForMessage(message), {
        disable_notification: true,
        ...Markup.removeKeyboard(),
      });
    } else {
      var markup;
      if (message.markup) {
        markup = Markup.keyboard(message.markup).oneTime().resize();
      } else {
        markup = Markup.removeKeyboard();
      }
      switch (message.type) {
        case "text":
          await ctx.replyWithMarkdownV2(escapeForMessage(message.text), {
            disable_notification: true,
            ...markup,
          });
          break;
        case "photo":
          await ctx.replyWithPhoto(message.file_id, {
            disable_notification: true,
            ...message.extra,
            ...markup,
          });
          break;
        case "location":
          await ctx.replyWithLocation(message.lat, message.lng, {
            disable_notification: true,
            ...markup,
          });
          break;
        case "document":
          await ctx.replyWithDocument(message.file_id, {
            caption: message.caption,
            ...markup,
          });
          break;
        default:
          console.error("Message type is unknown: %s", message);
          break;
      }
    }
  }
}
