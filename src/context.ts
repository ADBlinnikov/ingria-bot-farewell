import { Context } from "telegraf";

export interface MyContext extends Context {
  session: {
    skip_counter: number;
    try_counter: number;
    stage: number;
    feedback: string[];
  };
}
