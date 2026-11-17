import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "QuizForge — 퀴즈 생성 및 채점",
  description: "학습자료와 주제를 입력해 퀴즈를 생성하고 답안을 채점합니다.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body>{children}</body></html>;
}
