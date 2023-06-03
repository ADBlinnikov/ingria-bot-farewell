import {
  S3Client,
  GetObjectCommand,
  PutObjectCommand,
  DeleteObjectCommand,
  NoSuchKey,
} from "@aws-sdk/client-s3";

const s3 = new S3Client({
  endpoint: "https://storage.yandexcloud.net",
  region: "ru-central1",
});

export async function getS3Object(bucket: string, file: string, initial: any) {
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

export async function putStringToBucket(
  bucket: string,
  key: string,
  body: string
) {
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

export async function deleteS3Object(bucket: string, key: string) {
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
