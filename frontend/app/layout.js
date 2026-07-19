import "./styles.css";

export const metadata = {
  title: "UFC Winner Predictor",
  description: "Compare two UFC fighters using the trained winner model."
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
