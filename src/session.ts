import { Middleware, Context } from "telegraf";
import { Update } from "telegraf/types";
import { getS3Object, putStringToBucket, deleteS3Object } from "./s3";

type S3SessionConstructorOptions = {
  bucket: string;
  initial: () => object;
  store?: object;
  property?: string;
  getSessionKey?: (ctx: Context) => string;
};

type S3SessionOptions = {
  bucket: string;
  initial: () => object;
  store: object;
  property: string;
  getSessionKey: (ctx: Context) => string;
};

function getSessionKeyDefault(ctx: Context): string | null {
  if (!ctx.from || !ctx.chat) {
    return null;
  }
  return `session/${ctx.from.id}:${ctx.chat.id}`;
}

export class S3Session {
  options: S3SessionOptions;

  constructor(options: S3SessionConstructorOptions) {
    if (!options.bucket) {
      throw Error("S3 Bucket name not specified");
    }
    this.options = Object.assign(
      {
        property: "session",
        getSessionKey: getSessionKeyDefault,
        store: {},
      },
      options
    );
  }

  async getSession(key: string) {
    return await getS3Object(this.options.bucket, key, this.options.initial());
  }

  async clearSession(key: string) {
    console.debug("clear session %s", key);
    return await deleteS3Object(this.options.bucket, key);
  }

  async saveSession(key: string, session: string) {
    if (!session || Object.keys(session).length === 0) {
      return await this.clearSession(key);
    }
    return await putStringToBucket(
      this.options.bucket,
      key,
      JSON.stringify(session)
    );
  }

  middleware(): Middleware<Context<Update>> {
    return async (ctx, next) => {
      const key = this.options.getSessionKey(ctx);
      if (!key) {
        return await next();
      }
      let session = await this.getSession(key);
      Object.defineProperty(ctx, this.options.property, {
        get: function () {
          return session;
        },
        set: function (newValue) {
          session = Object.assign({}, newValue);
        },
      });
      await next();
      await this.saveSession(key, session);
    };
  }
}
