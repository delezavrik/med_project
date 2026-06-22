from app.schemas.query import AnswerResponse, ChatAskRequest, ParsedQuery, TemplateExecuteRequest
from app.services.answer_router import AnswerRouter
from app.services.chat_parser import ChatParser
from app.services.template_parser import TemplateParser
from app.services.tool_router import ToolRouter


class QueryService:
    def __init__(self) -> None:
        self.template_parser = TemplateParser()
        self.chat_parser = ChatParser()
        self.tool_router = ToolRouter()
        self.answer_router = AnswerRouter()

    def execute_parsed_query(self, query: ParsedQuery) -> AnswerResponse:
        structured_result = self.tool_router.run(query)
        return self.answer_router.build(query, structured_result)

    def execute_template(self, template_id: str, request: TemplateExecuteRequest) -> AnswerResponse:
        parsed_query = self.template_parser.parse(template_id, request)
        return self.execute_parsed_query(parsed_query)

    def ask_chat(self, request: ChatAskRequest) -> AnswerResponse:
        parsed_query = self.chat_parser.parse(request)
        return self.execute_parsed_query(parsed_query)
