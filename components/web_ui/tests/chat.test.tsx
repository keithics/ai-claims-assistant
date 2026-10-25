import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ApiError } from "../src/api/client";
import { makeApi, renderApp, reply } from "./helpers";

async function ready() {
  await screen.findByRole("option", { name: "Japan" });
}

function box() {
  return screen.getByLabelText("Type your message");
}

describe("chat", () => {
  it("loads the countries and offers each country's languages", async () => {
    renderApp(makeApi());
    await ready();
    const language = screen.getByLabelText("Language");
    expect(
      Array.from(language.querySelectorAll("option")).map((o) => o.textContent),
    ).toEqual(["English", "Filipino", "Cebuano"]);
  });

  it("shows an example claim number for the chosen country in the empty state", async () => {
    renderApp(makeApi());
    expect(await screen.findByText(/PH-1042/)).toBeInTheDocument();
  });

  it("sends the message and shows the answer, a citation link and the AI notice", async () => {
    const api = makeApi();
    const user = userEvent.setup();
    renderApp(api);
    await ready();
    await user.type(box(), "How many days do I have?");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText(/You have 30 days/)).toBeInTheDocument();
    expect(api.chat).toHaveBeenCalledWith({
      message: "How many days do I have?",
      country: "ph",
      language: "en",
      conversation_id: null,
      history: [],
    });
    const link = screen.getByRole("link", { name: "[1] Claim deadlines" });
    expect(link).toHaveAttribute("href", "/documents/ph-deadlines");
    expect(screen.getByText(/I am an AI assistant/)).toBeInTheDocument();
    expect(box()).toHaveValue("");
  });

  it("sends earlier turns as history and keeps the conversation id", async () => {
    const api = makeApi();
    const user = userEvent.setup();
    renderApp(api);
    await ready();
    await user.type(box(), "first{Enter}");
    await screen.findByText(/You have 30 days/);
    await user.type(box(), "second{Enter}");
    await waitFor(() => expect(api.chat).toHaveBeenCalledTimes(2));
    expect(api.chat.mock.calls[1]![0]).toMatchObject({
      message: "second",
      conversation_id: "conv-1",
      history: [
        { role: "user", content: "first" },
        {
          role: "assistant",
          content: "You have 30 days to report an incident [1].",
        },
      ],
    });
  });

  it("disables sending while a reply is pending and when the box is empty", async () => {
    let finish: (value: ReturnType<typeof reply>) => void = () => {};
    const api = makeApi({
      chat: () => new Promise((resolve) => (finish = resolve)),
    });
    const user = userEvent.setup();
    renderApp(api);
    await ready();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    await user.type(box(), "hello{Enter}");
    expect(
      await screen.findByRole("button", { name: "Thinking..." }),
    ).toBeDisabled();
    finish(reply());
    expect(
      await screen.findByRole("button", { name: "Send" }),
    ).toBeInTheDocument();
  });

  it("shows a friendly error when the service fails", async () => {
    const api = makeApi({
      chat: async () => {
        throw new ApiError(502, null, "model call failed");
      },
    });
    const user = userEvent.setup();
    renderApp(api);
    await ready();
    await user.type(box(), "hello{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong",
    );
  });

  it("starts a fresh conversation on request", async () => {
    const api = makeApi();
    const user = userEvent.setup();
    renderApp(api);
    await ready();
    await user.type(box(), "first{Enter}");
    await screen.findByText(/You have 30 days/);
    await user.click(screen.getByRole("button", { name: "New conversation" }));
    expect(screen.queryByText(/You have 30 days/)).not.toBeInTheDocument();
    await user.type(box(), "again{Enter}");
    await waitFor(() => expect(api.chat).toHaveBeenCalledTimes(2));
    expect(api.chat.mock.calls[1]![0]).toMatchObject({
      conversation_id: null,
      history: [],
    });
  });

  it("starts over and switches to the market's main language when the country changes", async () => {
    const api = makeApi();
    const user = userEvent.setup();
    renderApp(api);
    await ready();
    await user.type(box(), "hello{Enter}");
    await screen.findByText(/You have 30 days/);
    await user.selectOptions(screen.getByLabelText("Country"), "jp");
    expect(screen.queryByText(/You have 30 days/)).not.toBeInTheDocument();
    expect(screen.getByLabelText("言語")).toHaveValue("ja");
    await user.selectOptions(screen.getByLabelText("国"), "ph");
    expect(screen.getByLabelText("Language")).toHaveValue("en");
  });

  it("switches every UI string to the chosen language", async () => {
    const user = userEvent.setup();
    renderApp(makeApi());
    await ready();
    await user.selectOptions(screen.getByLabelText("Language"), "fil");
    expect(screen.getByRole("button", { name: "Ipadala" })).toBeInTheDocument();
    expect(screen.getByLabelText("Bansa")).toBeInTheDocument();
  });

  it("tells the user when the country list cannot be loaded", async () => {
    renderApp(
      makeApi({
        countries: async () => {
          throw new Error("down");
        },
      }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "countries could not be loaded",
    );
  });
});

describe("keyboard", () => {
  it("submits on Enter but not on Shift+Enter", async () => {
    const api = makeApi();
    const user = userEvent.setup();
    renderApp(api);
    await ready();
    await user.type(box(), "line one{Shift>}{Enter}{/Shift}line two");
    expect(api.chat).not.toHaveBeenCalled();
    expect(box()).toHaveValue("line one\nline two");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(api.chat).toHaveBeenCalledTimes(1));
  });

  it("does not submit while an IME composition is in progress", async () => {
    const api = makeApi();
    const user = userEvent.setup();
    renderApp(api);
    await ready();
    await user.type(box(), "こんにちは");
    fireEvent.compositionStart(box());
    fireEvent.keyDown(box(), { key: "Enter", isComposing: true });
    fireEvent.keyDown(box(), { key: "Enter", keyCode: 229 });
    expect(api.chat).not.toHaveBeenCalled();
    fireEvent.compositionEnd(box());
    fireEvent.keyDown(box(), { key: "Enter" });
    await waitFor(() => expect(api.chat).toHaveBeenCalledTimes(1));
  });
});

describe("Thai and Japanese", () => {
  it("renders a Thai conversation with the right language marks", async () => {
    const answer = "ต้องแจ้งเหตุภายใน 15 วัน นับจากวันเกิดเหตุ [1]";
    const api = makeApi({
      chat: async () => reply({ country: "th", language: "th", answer }),
    });
    const user = userEvent.setup();
    renderApp(api);
    await ready();
    await user.selectOptions(screen.getByLabelText("Country"), "th");
    expect(screen.getByLabelText("ภาษา")).toHaveValue("th");
    await user.type(
      screen.getByLabelText("พิมพ์ข้อความของคุณ"),
      "ต้องแจ้งเหตุภายในกี่วัน{Enter}",
    );
    const text = await screen.findByText(answer);
    expect(text.closest("[lang]")).toHaveAttribute("lang", "th");
    expect(
      screen.getByText("ต้องแจ้งเหตุภายในกี่วัน").closest("[lang]"),
    ).toHaveAttribute("lang", "th");
    expect(screen.getByRole("button", { name: "ส่ง" })).toBeInTheDocument();
    expect(
      document.documentElement.querySelector('[lang="th"].root'),
    ).not.toBeNull();
  });

  it("renders a Japanese conversation in polite form with the right language marks", async () => {
    const answer = "事故の日から60日以内にご連絡ください。[1]";
    const api = makeApi({
      chat: async () => reply({ country: "jp", language: "ja", answer }),
    });
    const user = userEvent.setup();
    renderApp(api);
    await ready();
    await user.selectOptions(screen.getByLabelText("Country"), "jp");
    expect(screen.getByLabelText("言語")).toHaveValue("ja");
    await user.type(
      screen.getByLabelText("メッセージを入力"),
      "連絡は何日以内ですか{Enter}",
    );
    const text = await screen.findByText(answer);
    expect(text.closest("[lang]")).toHaveAttribute("lang", "ja");
    expect(screen.getByRole("button", { name: "送信" })).toBeInTheDocument();
    expect(api.chat.mock.calls[0]![0]).toMatchObject({
      country: "jp",
      language: "ja",
    });
  });
});

describe("source documents", () => {
  it("opens a cited document", async () => {
    const api = makeApi();
    const user = userEvent.setup();
    renderApp(api);
    await ready();
    await user.type(box(), "deadline{Enter}");
    await user.click(
      await screen.findByRole("link", { name: "[1] Claim deadlines" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Claim deadlines" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Report within 30 days/)).toBeInTheDocument();
    expect(api.document).toHaveBeenCalledWith("ph-deadlines");
    expect(screen.getByRole("link", { name: "Back to chat" })).toHaveAttribute(
      "href",
      "/",
    );
  });

  it("says so when the document does not exist", async () => {
    const api = makeApi({
      document: async () => {
        throw new ApiError(404, null, "no document");
      },
    });
    renderApp(api, "/documents/nope");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "could not be found",
    );
  });
});

describe("accessibility", () => {
  it("labels every control and offers a skip link and landmarks", async () => {
    renderApp(makeApi());
    await ready();
    expect(
      screen.getByRole("link", { name: "Skip to content" }),
    ).toHaveAttribute("href", "#main");
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", { name: "Main" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Country")).toBeInTheDocument();
    expect(screen.getByLabelText("Language")).toBeInTheDocument();
    expect(box()).toBeInTheDocument();
    for (const control of screen.getAllByRole("button")) {
      expect(control).toHaveAccessibleName();
    }
  });

  it("announces new messages politely", async () => {
    const user = userEvent.setup();
    renderApp(makeApi());
    await ready();
    await user.type(box(), "hi{Enter}");
    expect(await screen.findByRole("log")).toHaveAttribute(
      "aria-live",
      "polite",
    );
  });
});
