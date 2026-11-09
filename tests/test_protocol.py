"""Tool-call parsing must survive the ways small models mangle the wire format."""
import unittest

from medibuddy_bench.protocol import parse_agent_reply


class ToolCallParsing(unittest.TestCase):
    def call(self, text):
        return parse_agent_reply(text)[2]

    def test_canonical(self):
        self.assertEqual(self.call('<tool_call>{"name": "a", "args": {"k": 1}}</tool_call>'),
                         {"name": "a", "args": {"k": 1}})

    def test_llama_style_missing_bracket_and_semicolon(self):
        """Seen from llama3.2:3b: `<tool_call {...};</tool_call>`, several calls in one reply -> only the first counts."""
        t = ('<tool_call {"name": "list_districts", "args": {}};</tool_call>\n'
             '<tool_call {"name": "distance_km", "args": {"from_district": "A", "to_district": "B"}};</tool_call>')
        self.assertEqual(self.call(t), {"name": "list_districts", "args": {}})

    def test_missing_close_tag_and_arg_aliases(self):
        self.assertEqual(self.call('<tool_call>{"name": "a", "arguments": {"k": 1}}'), {"name": "a", "args": {"k": 1}})

    def test_fence_and_bare_json_only_when_reply_is_just_the_call(self):
        self.assertEqual(self.call('```json\n{"name": "a", "args": {}}\n```'), {"name": "a", "args": {}})
        self.assertEqual(self.call('{"name": "b", "args": {"x": 2}}'), {"name": "b", "args": {"x": 2}})
        self.assertIsNone(self.call('I will use {"name": "b", "args": {}} later, thanks'))

    def test_final_answer_and_junk_are_not_calls(self):
        text, data, call = parse_agent_reply('Go to H0001. <answer>{"recommendations": []}</answer>')
        self.assertEqual((text, data, call), ("Go to H0001.", {"recommendations": []}, None))
        self.assertIsNone(self.call("<tool_call>not json</tool_call>"))


if __name__ == "__main__":
    unittest.main()
