import { Context } from "telegraf";

export interface MyContext extends Context {
  session: {
    skip_counter: number;
    stage: number;
  };
}

export function initialState() {
  return { skip_counter: 0, stage: 0 };
}
