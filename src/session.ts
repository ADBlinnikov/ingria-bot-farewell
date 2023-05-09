import {
  S3Client,
  GetObjectCommand,
  PutObjectCommand,
  DeleteObjectCommand,
  NoSuchKey,
} from "@aws-sdk/client-s3";
import { Middleware, Context } from "telegraf";
import { Update } from "telegraf/types";

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

const s3 = new S3Client({
  endpoint: "https://storage.yandexcloud.net",
  region: "ru-central1",
});

function getSessionKeyDefault(ctx: Context): string | null {
  if (!ctx.from || !ctx.chat) {
    return null;
  }
  return `${ctx.from.id}:${ctx.chat.id}`;
}

async function getS3Object(bucket: string, file: string, initial: any) {
  try {
    const data = await s3.send(
      new GetObjectCommand({
        Bucket: bucket,
        Key: String(file),
      })
    );
    const content = await data.Body?.transformToString();
    console.debug("s3 Object content: %s", content);
    if (typeof content === "string") {
      return JSON.parse(content);
    } else {
      return initial;
    }
  } catch (error) {
    if (error instanceof NoSuchKey) {
      return initial;
    }
    return;
  }
}

async function putStringToBucket(bucket: string, key: string, body: string) {
  try {
    const data = await s3.send(
      new PutObjectCommand({
        Bucket: bucket,
        Key: String(key),
        Body: Buffer.from(body, "utf-8"),
      })
    );
    return data;
  } catch (error) {
    console.error("Cannot put S3 object:", error);
  }
}

async function deleteS3Object(bucket: string, key: string) {
  try {
    const data = await s3.send(
      new DeleteObjectCommand({
        Bucket: bucket,
        Key: String(key),
      })
    );
    return data;
  } catch (error) {
    console.error("Cannot delete S3 object:", error);
  }
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
