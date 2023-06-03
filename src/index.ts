import { Handler } from "@yandex-cloud/function-types";
import { Telegraf } from "telegraf";
import { firstStep, stepProcessor } from "./logic";
import { S3Session } from "./session";
import { MyContext, initialState } from "./context";

// Declare bot
const bot = new Telegraf<MyContext>(process.env.BOT_TOKEN!);

// Middleware
const s3Session = new S3Session({
  bucket: process.env.S3_STATES_BUCKET!,
  initial: initialState,
});
bot.use(s3Session.middleware());

// First step
bot.start(firstStep);
bot.command("stage", (ctx) => {
  let stageToSet = ctx.message.text.split(" ")[1];
  if (stageToSet) {
    ctx.session.stage = parseInt(stageToSet);
    ctx.reply("Stage is set");
  } else {
    ctx.reply("Current stage: " + ctx.session.stage);
  }
});
// Extract method to separate file
bot.on("text", stepProcessor);

// Enable graceful stop
process.once("SIGINT", () => bot.stop("SIGINT"));
process.once("SIGTERM", () => bot.stop("SIGTERM"));

// For local testing
// bot.launch();

// For run
export const handler: Handler.Http = async (event, context) => {
  const message = JSON.parse(event.body);
  await bot.handleUpdate(message);
  return {
    statusCode: 200,
    body: "",
  };
};
