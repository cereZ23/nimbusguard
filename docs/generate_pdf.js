const { chromium } = require("playwright");
const path = require("path");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  const htmlPath = path.resolve(__dirname, "pitch_cspm.html");
  await page.goto(`file://${htmlPath}`, { waitUntil: "networkidle" });

  await page.pdf({
    path: path.resolve(__dirname, "pitch_nimbusguard_cspm.pdf"),
    format: "A4",
    printBackground: true,
    margin: { top: "0", right: "0", bottom: "0", left: "0" },
  });

  await browser.close();
  console.log("PDF generated: pitch_nimbusguard_cspm.pdf");
})();
