import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../src/api/client";
import { ApprovalCard } from "../src/features/approval/ApprovalCard";
import { I18nProvider } from "../src/i18n/I18nProvider";
import type { ApprovalItem } from "../src/state/conversation-context";
import {
  draft,
  filedResponse,
  makeApi,
  pending,
  renderApp,
  reply,
} from "./helpers";

async function openApprovals(api: ReturnType<typeof makeApi>) {
  const user = userEvent.setup();
  renderApp(api);
  await screen.findByRole("option", { name: "Japan" });
  await user.type(
    screen.getByLabelText("Type your message"),
    "I want to file a claim{Enter}",
  );
  await user.click(await screen.findByRole("link", { name: "Review" }));
  await screen.findByRole("heading", { name: "PH-5001" });
  return user;
}

function withDraft() {
  return makeApi({
    chat: async () => reply({ pending_approvals: [pending()] }),
  });
}

describe("approval screen", () => {
  it("shows a banner and a badge when a draft is waiting", async () => {
    const user = userEvent.setup();
    renderApp(withDraft());
    await screen.findByRole("option", { name: "Japan" });
    await user.type(
      screen.getByLabelText("Type your message"),
      "file it{Enter}",
    );
    expect(
      await screen.findByText(/Claims waiting for your approval: 1/),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("navigation")).getByText("1"),
    ).toBeInTheDocument();
  });

  it("shows the drafted claim with its details", async () => {
    await openApprovals(withDraft());
    const card = screen.getByRole("article");
    expect(within(card).getByText("Motor")).toBeInTheDocument();
    expect(within(card).getByText("2026-10-20")).toBeInTheDocument();
    expect(
      within(card).getByText("Rear-ended at a junction"),
    ).toBeInTheDocument();
    expect(within(card).getByText("12000 PHP")).toBeInTheDocument();
    expect(within(card).getByText("Not provided")).toBeInTheDocument();
    expect(within(card).getByText("Draft")).toBeInTheDocument();
    expect(
      screen.getByText("Nothing is filed until you approve it here."),
    ).toBeInTheDocument();
  });

  it("approves with the token and shows the filed claim", async () => {
    const api = withDraft();
    const user = await openApprovals(api);
    await user.click(screen.getByRole("button", { name: "Approve and file" }));
    expect(
      await screen.findByText("Claim PH-5001 was filed."),
    ).toBeInTheDocument();
    expect(api.approve).toHaveBeenCalledWith({
      claim_id: "PH-5001",
      token: "tok.sig",
    });
    expect(
      screen.queryByRole("button", { name: "Approve and file" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Reject" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Submitted")).toBeInTheDocument();
    expect(
      within(screen.getByRole("navigation")).queryByText("1"),
    ).not.toBeInTheDocument();
  });

  it("rejects the draft without filing it", async () => {
    const api = withDraft();
    const user = await openApprovals(api);
    await user.click(screen.getByRole("button", { name: "Reject" }));
    expect(
      await screen.findByText(/You rejected the draft for claim PH-5001/),
    ).toBeInTheDocument();
    expect(api.reject).toHaveBeenCalledWith({
      claim_id: "PH-5001",
      token: "tok.sig",
    });
    expect(api.approve).not.toHaveBeenCalled();
    expect(
      screen.queryByRole("button", { name: "Approve and file" }),
    ).not.toBeInTheDocument();
  });

  it("explains an expired approval and offers no buttons", async () => {
    const api = withDraft();
    api.approve.mockRejectedValue(
      new ApiError(410, "token_expired", "approval token has expired"),
    );
    const user = await openApprovals(api);
    await user.click(screen.getByRole("button", { name: "Approve and file" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This approval expired",
    );
    expect(
      screen.queryByRole("button", { name: "Approve and file" }),
    ).not.toBeInTheDocument();
  });

  it("explains an approval that was already used", async () => {
    const api = withDraft();
    api.approve.mockRejectedValue(new ApiError(409, "token_used", "used"));
    const user = await openApprovals(api);
    await user.click(screen.getByRole("button", { name: "Approve and file" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already used");
  });

  it("shows the server's message for any other API error", async () => {
    const api = withDraft();
    api.approve.mockRejectedValue(
      new ApiError(400, "token_invalid", "the draft changed"),
    );
    const user = await openApprovals(api);
    await user.click(screen.getByRole("button", { name: "Approve and file" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The claim could not be filed: the draft changed",
    );
  });

  it("lets the user retry when the claims system is down", async () => {
    const api = withDraft();
    api.approve.mockRejectedValueOnce(new ApiError(503, "unavailable", "down"));
    api.approve.mockResolvedValueOnce(filedResponse());
    const user = await openApprovals(api);
    await user.click(screen.getByRole("button", { name: "Approve and file" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "not responding",
    );
    await user.click(screen.getByRole("button", { name: "Approve and file" }));
    expect(
      await screen.findByText("Claim PH-5001 was filed."),
    ).toBeInTheDocument();
    expect(api.approve).toHaveBeenCalledTimes(2);
  });

  it("treats a lost network connection like an outage", async () => {
    const api = withDraft();
    api.approve.mockRejectedValue(new ApiError(0, "network", "unreachable"));
    const user = await openApprovals(api);
    await user.click(screen.getByRole("button", { name: "Approve and file" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "not responding",
    );
    expect(
      screen.getByRole("button", { name: "Approve and file" }),
    ).toBeEnabled();
  });

  it("disables both buttons while the request is running", async () => {
    let finish: () => void = () => {};
    const api = withDraft();
    api.approve.mockImplementation(
      () => new Promise((resolve) => (finish = () => resolve(filedResponse()))),
    );
    const user = await openApprovals(api);
    await user.click(screen.getByRole("button", { name: "Approve and file" }));
    expect(
      await screen.findByRole("button", { name: "Working..." }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled();
    finish();
    await waitFor(() =>
      expect(screen.getByText("Claim PH-5001 was filed.")).toBeInTheDocument(),
    );
  });

  it("says when nothing is waiting", async () => {
    renderApp(makeApi(), "/approvals");
    expect(
      await screen.findByText("There is no claim waiting for your approval."),
    ).toBeInTheDocument();
  });

  it("does not list the same draft twice", async () => {
    const api = makeApi({
      chat: async () => reply({ pending_approvals: [pending()] }),
    });
    const user = userEvent.setup();
    renderApp(api);
    await screen.findByRole("option", { name: "Japan" });
    await user.type(screen.getByLabelText("Type your message"), "one{Enter}");
    await screen.findByText(/Claims waiting for your approval: 1/);
    await user.type(screen.getByLabelText("Type your message"), "two{Enter}");
    await waitFor(() => expect(api.chat).toHaveBeenCalledTimes(2));
    expect(
      screen.getByText(/Claims waiting for your approval: 1/),
    ).toBeInTheDocument();
  });
});

describe("ApprovalCard", () => {
  function item(overrides: Partial<ApprovalItem> = {}): ApprovalItem {
    return {
      claimId: "PH-5001",
      token: "t",
      expiresAt: 1_900_000_000,
      draft: draft({ amount_claimed: null, policy_number: "POL-PH-1207280" }),
      status: "pending",
      ...overrides,
    };
  }

  function show(value: ApprovalItem, language: "en" | "th" | "ja" = "en") {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    render(
      <I18nProvider language={language}>
        <ApprovalCard item={value} onApprove={onApprove} onReject={onReject} />
      </I18nProvider>,
    );
    return { onApprove, onReject };
  }

  it("shows the policy number and a missing amount", () => {
    show(item());
    expect(screen.getByText("POL-PH-1207280")).toBeInTheDocument();
    expect(screen.getByText("Not provided")).toBeInTheDocument();
  });

  it("calls back with the claim id", async () => {
    const { onApprove, onReject } = show(item());
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Approve and file" }));
    await user.click(screen.getByRole("button", { name: "Reject" }));
    expect(onApprove).toHaveBeenCalledWith("PH-5001");
    expect(onReject).toHaveBeenCalledWith("PH-5001");
  });

  it("is localized", () => {
    show(item(), "ja");
    expect(
      screen.getByRole("button", { name: "承認して提出" }),
    ).toBeInTheDocument();
    expect(screen.getByText("自動車")).toBeInTheDocument();
  });

  it("shows the Thai buttons and an unknown claim type as is", () => {
    show(item({ draft: draft({ claim_type: "boat" }) }), "th");
    expect(
      screen.getByRole("button", { name: "อนุมัติและยื่นเคลม" }),
    ).toBeInTheDocument();
    expect(screen.getByText("boat")).toBeInTheDocument();
  });
});
