from app.schemas.query import AnswerMode, ChatAskRequest, Intent, ParsedQuery, QuerySource, ReviewFilters, ToolName


class ChatParser:
    """Преобразует вопрос пользователя в ParsedQuery.

    Сейчас это безопасный rule-based fallback для MVP.
    Позже сюда подключается LLM function calling / JSON schema parser.
    """

    def parse(self, request: ChatAskRequest) -> ParsedQuery:
        text = request.message.lower()

        labels: list[str] = []
        if "достав" in text or "получ" in text:
            labels.append("Проблема доставки / получения")
        if "упаков" in text or "комплект" in text:
            labels.append("Проблема с комплектацией / упаковкой")
        if "брак" in text or "дефект" in text or "качеств" in text:
            labels.append("Проблема с качеством товара")
        if "размер" in text or "посад" in text or "маломер" in text:
            labels.append("Проблема с размером / посадкой")
        if "описан" in text or "карточк" in text or "не соответств" in text:
            labels.append("Несоответствие карточке товара")
        if "цен" in text or "дорог" in text:
            labels.append("Цена / ценность")
        if "возврат" in text:
            labels.append("Проблема с возвратом")

        category = None

        if "пример" in text or "похож" in text or "покажи отзывы" in text:
            intent = Intent.REVIEW_EXAMPLES
            tools = [ToolName.QDRANT]
            answer_mode = AnswerMode.TEMPLATE
            semantic_query = request.message
        elif "что стало хуже" in text or "почему" in text or "вывод" in text or "рекоменда" in text:
            intent = Intent.PROBLEM_GROWTH_ANALYSIS
            tools = [ToolName.POSTGRES, ToolName.QDRANT]
            answer_mode = AnswerMode.LLM
            semantic_query = request.message
        elif "топ" in text or "главн" in text:
            intent = Intent.TOP_PROBLEMS
            tools = [ToolName.POSTGRES]
            answer_mode = AnswerMode.TEMPLATE
            semantic_query = None
        else:
            intent = Intent.COUNT_BY_PROBLEM
            tools = [ToolName.POSTGRES]
            answer_mode = AnswerMode.TEMPLATE
            semantic_query = None

        if request.force_answer_mode:
            answer_mode = AnswerMode(request.force_answer_mode)

        return ParsedQuery(
            source=QuerySource.CHAT,
            intent=intent,
            filters=ReviewFilters(labels=labels, category=category),
            semantic_query=semantic_query,
            tools=tools,
            answer_mode=answer_mode,
        )
