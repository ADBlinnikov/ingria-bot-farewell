import { Handler } from "@yandex-cloud/function-types";
import { Context, Telegraf } from "telegraf";
import { send } from "./send";
import { S3Session } from "./session";
import { content } from "./content";
import { validate } from "./validate";

const SKIP_MAX = 5;

// Define context type
interface MyContext extends Context {
  session: {
    skip_counter: number;
    try_counter: number;
    stage: number;
  };
}

// Markup

// Declare bot
const bot = new Telegraf<MyContext>(process.env.BOT_TOKEN!);

// Middleware
const s3Session = new S3Session({
  bucket: process.env.S3_STATES_BUCKET!,
  initial: () => ({ skip_counter: 0, try_counter: 0, stage: 0 }),
});
bot.use(s3Session.middleware());

// Logic
function get_random_congrats(): string {
  return content.success[Math.floor(Math.random() * content.success.length)];
}
bot.start(async (ctx) => {
  const stage = content.stages[0];
  await send(ctx, stage.messages || [], stage.markup);
  ctx.session.stage = 1;
});
bot.on("text", async (ctx) => {
  const stage = content.stages[ctx.session.stage];
  console.log(
    "User: %d (%s) Stage: %s Message: %s",
    ctx.from.id,
    ctx.from.username,
    stage.name,
    ctx.message.text
  );
  if (stage.condition) {
    const user_answered = validate(ctx.message.text, stage.condition);
    const user_skiped = ctx.message.text.toLowerCase().includes("пропустить");
    const lives_left = SKIP_MAX - ctx.session.skip_counter;
    if (user_answered) {
      await send(ctx, [get_random_congrats()]);
    } else if (lives_left > 0 && user_skiped) {
      ctx.session.skip_counter++;
    } else {
      if (lives_left > 0) {
        await send(ctx, [content.try_again_text + lives_left], ["Пропустить"]);
      } else {
        await send(ctx, [content.wrong_answer_text]);
      }
      return;
    }
  }
  await send(ctx, stage.messages || [], stage.markup);
  // Set next state if possible
  if (ctx.session.stage < content.stages.length - 1) {
    ctx.session.stage++;
  }
});

// Enable graceful stop
process.once("SIGINT", () => bot.stop("SIGINT"));
process.once("SIGTERM", () => bot.stop("SIGTERM"));

export const handler: Handler.Http = async (event, context) => {
  const message = JSON.parse(event.body);
  await bot.handleUpdate(message);
  return {
    statusCode: 200,
    body: "",
  };
};
