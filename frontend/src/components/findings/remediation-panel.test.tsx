import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import RemediationPanel, { type RemediationData } from "./remediation-panel";

// CopyButton uses navigator.clipboard which is not available in jsdom.
// Mock it to a no-op so the panel renders without errors.
vi.mock("./copy-button", () => ({
  default: () => <button>Copy</button>,
}));

function makeRemediation(
  overrides: Partial<RemediationData> = {},
): RemediationData {
  return {
    control_code: "CIS-AZ-23",
    control_name: "Web app HTTPS only",
    description: "Enforce HTTPS on the web app",
    remediation_hint: "Set httpsOnly=true",
    snippets: {
      terraform:
        'resource "azurerm_linux_web_app" "example" { name = "myapp" }',
      bicep:
        "resource webApp 'Microsoft.Web/sites@2022-09-01' = { name: 'myapp' }",
      azure_cli:
        "az webapp update --name myapp --resource-group rg-prod --set httpsOnly=true",
    },
    filled_for_asset: false,
    asset_name: null,
    ...overrides,
  };
}

describe("RemediationPanel", () => {
  it("renders the remediation guidance header and hint", () => {
    render(<RemediationPanel remediation={makeRemediation()} />);
    expect(screen.getByText(/Remediation Guidance/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Enforce HTTPS on the web app/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Set httpsOnly=true/i)).toBeInTheDocument();
  });

  it("shows the Filled for <asset> badge when filled_for_asset is true", () => {
    render(
      <RemediationPanel
        remediation={makeRemediation({
          filled_for_asset: true,
          asset_name: "ifoprod-api",
        })}
      />,
    );
    expect(screen.getByText(/Filled for ifoprod-api/i)).toBeInTheDocument();
  });

  it("does NOT show the badge when filled_for_asset is false", () => {
    render(<RemediationPanel remediation={makeRemediation()} />);
    expect(screen.queryByText(/Filled for/i)).not.toBeInTheDocument();
  });

  it("does NOT show the badge when asset_name is missing", () => {
    render(
      <RemediationPanel
        remediation={makeRemediation({
          filled_for_asset: true,
          asset_name: null,
        })}
      />,
    );
    expect(screen.queryByText(/Filled for/i)).not.toBeInTheDocument();
  });

  it("warns when the active snippet has unfilled @@markers@@", () => {
    render(
      <RemediationPanel
        remediation={makeRemediation({
          snippets: {
            terraform: 'name = "@@name@@" rg = "@@workspace_id@@"',
            bicep: null,
            azure_cli: null,
          },
        })}
      />,
    );
    expect(
      screen.getByText(/still need to be filled in manually/i),
    ).toBeInTheDocument();
  });

  it("does NOT warn when the active snippet is fully resolved", () => {
    render(
      <RemediationPanel
        remediation={makeRemediation({
          filled_for_asset: true,
          asset_name: "myapp",
          snippets: {
            terraform: 'name = "myapp"',
            bicep: null,
            azure_cli: null,
          },
        })}
      />,
    );
    expect(
      screen.queryByText(/still need to be filled in manually/i),
    ).not.toBeInTheDocument();
  });

  it("renders fallback hint when no remediation data but a hint is provided", () => {
    render(
      <RemediationPanel
        remediation={null}
        fallbackHint="Generic fallback hint"
      />,
    );
    expect(screen.getByText(/Generic fallback hint/i)).toBeInTheDocument();
  });

  it("renders nothing when no remediation and no fallback", () => {
    const { container } = render(<RemediationPanel remediation={null} />);
    expect(container.firstChild).toBeNull();
  });
});
