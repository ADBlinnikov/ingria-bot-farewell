import { Context, Markup } from "telegraf";
import { InlineKeyboardMarkup, ReplyKeyboardRemove } from "telegraf/types";

export type MessagePhoto = {
  type: "photo";
  photo: string;
  extra: {
    caption?: string;
  };
};
export type MessageLocation = {
  type: "location";
  lat: number;
  lng: number;
};
export type Message = string | MessagePhoto | MessageLocation;

export async function send(
  ctx: Context,
  messages: Message[],
  buttons?: string[]
) {
  var markup;
  if (buttons) {
    markup = Markup.keyboard(buttons).oneTime().resize();
  } else {
    markup = Markup.removeKeyboard();
  }
  for (let message of messages) {
    if (typeof message === "string") {
      await ctx.replyWithMarkdownV2(message, {
        disable_notification: true,
        ...markup,
      });
    } else {
      switch (message.type) {
        case "photo":
          await ctx.replyWithPhoto(message.photo, {
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
      }
    }
  }
}
