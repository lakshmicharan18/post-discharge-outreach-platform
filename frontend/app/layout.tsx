import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Post-Discharge Outreach Platform",
  description: "Multi-hospital post-discharge operations platform",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
