import typing
import re
from SymbolTable import *
from ScopeHandler import ScopeEntry
import SemanticChecker
from SemanticChecker import semantic_check

symbol_table = SymbolTable()
program_block = {}
program_block_counter = 0
semantic_stack = []
repeat_until_scope_stack = []
repeat_until_scope_stack: typing.List[ScopeEntry]


def write_to_program_block(*, code: str):
    global program_block_counter
    program_block[program_block_counter] = code
    program_block_counter += 1


def edit_program_line(line: int, replacement: str):
    program_block[line] = program_block[line].replace('?', replacement)


class FunctionEntry:
    def __init__(self, *, frame_size: int, lexeme: str):
        self.frame_size = frame_size
        self.lexeme = lexeme


new_symbol_table = NewSymbolTable()
scope_stack = [0]
scope_counter = 1
function_memory = []
function_memory: typing.List[FunctionEntry]

function_signature = dict()
write_to_program_block(code="(ASSIGN, #%s, %s, )" % (500, new_symbol_table.stack_pointer))
write_to_program_block(code="(ASSIGN, #0, %s, )" % new_symbol_table.return_value_address_pointer)

new_symbol_table.define_symbol(
    Symbol(lexeme='output', var_type='void', addressing_type="nothing",
           address=0, symbol_type='function', scope=0,
           arguments_count=1))


def get_by_relative_address(relative_address: int):
    temp = new_symbol_table.get_simple_temp()
    write_to_program_block(code="(ADD, %s, #%s, %s)" % (new_symbol_table.stack_pointer, relative_address, temp))
    return "@" + str(temp)


def get_pointer_by_relative_address(relative_address: int):
    pointer_address = get_by_relative_address(relative_address)
    temp = new_symbol_table.get_simple_temp()
    write_to_program_block(code="(ASSIGN, %s, %s, )" % (pointer_address, temp))
    return "@" + str(temp)


def at_at_to_at(pointer: str):
    temp = new_symbol_table.get_simple_temp()
    write_to_program_block(code="(ASSIGN, %s, %s, )" % (pointer, temp))
    return '@' + str(temp)


def get_symbol_address(symbol, real_address: bool = True):
    if symbol is None:
        return None
    if symbol.type == 'function':
        raise Exception('extracting address from function')
    if symbol.addressing_type == 'global':
        return symbol.address
    elif symbol.addressing_type == 'relative':
        return get_by_relative_address(symbol.address)
    elif symbol.addressing_type == 'relative pointer':
        return at_at_to_at(get_by_relative_address(symbol.address))
    else:
        raise Exception("hendelll")


def function_call(function_symbol: Symbol, args: list):
    if function_symbol is None:
        semantic_stack.append(None)
        return
    if len(args) != function_symbol.arguments_count:
        semantic_check(check_error='arguments_count', p1=function_symbol.lexeme)
        semantic_stack.append(None)
        return
    if function_symbol.lexeme == 'output':
        write_to_program_block(code="(PRINT, %s, , )" % get_symbol_address(args[0]))
        semantic_stack.append('output function void')
        return

    new_stack_pointer_address = new_symbol_table.get_simple_temp()
    write_to_program_block(code="(ADD, %s, #%s, %s)" % (
        new_symbol_table.stack_pointer, function_memory[-1].frame_size, new_stack_pointer_address))
    write_to_program_block(
        code="(ASSIGN, %s, @%s, )" % (new_symbol_table.stack_pointer, new_stack_pointer_address))

    return_line_address = new_symbol_table.get_simple_temp()
    write_to_program_block(code="(ADD, %s, #%s, %s)" % (
        new_symbol_table.stack_pointer, function_memory[-1].frame_size + 4, return_line_address))
    for i, arg in enumerate(args):
        if function_signature[function_symbol.lexeme][3 * i + 2] == 'array' and arg.var_type == 'int':
            semantic_check(check_error='argument_type', p1=i + 1, p2=function_symbol.lexeme, p3='array', p4='int')
        elif function_signature[function_symbol.lexeme][3 * i + 2] != 'array' and arg.var_type == 'int*':
            semantic_check(check_error='argument_type', p1=i + 1, p2=function_symbol.lexeme, p3='int', p4='array')
        arg_address_pointer = new_symbol_table.get_simple_temp()
        write_to_program_block(
            code="(ADD, %s, #%s, %s)" % (
                new_symbol_table.stack_pointer, function_memory[-1].frame_size + 8 + i * 4, arg_address_pointer))
        write_to_program_block(
            code="(ASSIGN, %s, @%s, )" % (get_symbol_address(arg), arg_address_pointer))

    write_to_program_block(
        code="(ASSIGN, %s, %s, )" % (new_stack_pointer_address, new_symbol_table.stack_pointer))
    write_to_program_block(code="(ASSIGN, #%s, @%s, )" % (program_block_counter + 2, return_line_address))
    write_to_program_block(code="(JP, %s, ,)" % function_symbol.address)
    relative_address = function_memory[-1].frame_size
    function_result_address = get_by_relative_address(relative_address)
    function_memory[-1].frame_size += 4
    write_to_program_block(
        code="(ASSIGN, %s, %s, )" % (new_symbol_table.return_value_address_pointer, function_result_address))
    semantic_stack.append(
        Symbol(lexeme="", var_type=function_symbol.var_type, addressing_type='relative', address=relative_address,
               scope=-1, symbol_type='variable')
    )


def exit_function_code():
    return_line_address_pointer = new_symbol_table.get_simple_temp()
    write_to_program_block(
        code=("(ADD, %s, #%s, %s)" % (new_symbol_table.stack_pointer, 4, return_line_address_pointer)))
    write_to_program_block(
        code="(ASSIGN, @%s, %s, )" % (new_symbol_table.stack_pointer, new_symbol_table.stack_pointer)
    )
    at_at_address = new_symbol_table.get_simple_temp()
    write_to_program_block(code="(ASSIGN, @%s, %s, )" % (return_line_address_pointer, at_at_address))
    write_to_program_block(
        code=("(JP, @%s, ,)" % at_at_address)
    )


def generate_code(*, action: str, label: str):
    global program_block_counter
    global scope_counter
    if action == '#push_type':
        def_type = re.match(r'\((\w+), (\w+)\)', label).group(2)
        semantic_stack.append(def_type)
    elif action == '#push_array_input_type':
        semantic_stack.append("array")
    elif action == '#push_normal_input_type':
        semantic_stack.append("nothing")
    elif action == '#add_param':
        lexeme = semantic_stack[-2]
        input_type = semantic_stack[-1]
    elif action == '#define_function':
        ss = []
        while semantic_stack[-1] != 'function_start':
            ss.append(semantic_stack.pop())
        semantic_stack.pop()
        ss.append(semantic_stack.pop())
        ss.append(semantic_stack.pop())
        ss = list(reversed(ss))
        function_type = ss[0]
        function_name = ss[1]
        args_count = (len(ss) - 2) // 3
        if function_name != 'main':
            write_to_program_block(code="(JP, ?, , )")
            semantic_stack.append(program_block_counter - 1)
        new_symbol_table.define_symbol(
            Symbol(lexeme=function_name, var_type=function_type, addressing_type="code_line",
                   address=program_block_counter, symbol_type='function', scope=scope_stack[-1],
                   arguments_count=args_count))
        scope_counter += 1
        scope_stack.append(scope_counter)
        function_memory.append(FunctionEntry(frame_size=8,
                                             lexeme=function_name))
        args = ss[2:]
        function_signature[function_name] = args
        i = 0
        while i < len(args):
            input_type = args[i]
            input_lexeme = args[i + 1]
            is_array = args[i + 2]
            var_type = input_type + ('*' if is_array == 'array' else '')
            new_symbol_table.define_symbol(
                Symbol(lexeme=input_lexeme, var_type=var_type, addressing_type='relative',
                       address=function_memory[-1].frame_size,
                       scope=scope_stack[-1], symbol_type='variable')
            )
            function_memory[-1].frame_size += 4
            i += 3
    elif action == '#END_SCOPE':
        new_symbol_table.remove_scope(scope_number=scope_stack.pop())
    elif action == '#return':
        exit_function_code()
    elif action == '#return_value':
        return_value = get_symbol_address(semantic_stack.pop())
        write_to_program_block(
            code="(ASSIGN, %s, %s, )" % (return_value, new_symbol_table.return_value_address_pointer))
        exit_function_code()
    elif action == '#end_function':
        function_entry = function_memory.pop()
        if function_entry.lexeme != 'main':
            exit_function_code()
            function_jump_over_line = semantic_stack.pop()
            edit_program_line(line=function_jump_over_line, replacement=str(program_block_counter))
    elif action == '#function_call':
        ss = []
        while semantic_stack[-1] != 'function_call':
            ss.append(semantic_stack.pop())
        semantic_stack.pop()
        function_symbol = semantic_stack.pop()
        ss = list(reversed(ss))
        function_call(function_symbol, ss)
    elif action == '#push':
        token = re.match(r'\((\w+), (\w+)\)', label).group(2)
        semantic_stack.append(token)
    elif action == '#start_function':
        semantic_stack.append("function_start")
    elif action == '#start_function_call':
        semantic_stack.append("function_call")
    elif action == '#variable_definition':
        var_type = semantic_stack[-2]
        var_name = semantic_stack[-1]
        semantic_stack.pop()
        semantic_stack.pop()
        if var_type == 'void':
            semantic_check(check_error='void_var', p1=var_name)
            return
        if len(function_memory) <= 0:
            symbol = Symbol(lexeme=var_name, var_type='int', addressing_type='global',
                            address=new_symbol_table.get_new_global_address(), scope=scope_stack[-1],
                            symbol_type='variable')
        else:
            symbol = Symbol(lexeme=var_name, var_type='int', addressing_type="relative",
                            address=function_memory[-1].frame_size, scope=scope_stack[-1], symbol_type='variable')
            function_memory[-1].frame_size += 4
        new_symbol_table.define_symbol(symbol)
    elif action == '#define_array':
        var_type = semantic_stack[-3]
        var_name = semantic_stack[-2]
        length = int(semantic_stack[-1])
        semantic_stack.pop()
        semantic_stack.pop()
        semantic_stack.pop()
        if var_type == 'void':
            semantic_check(check_error='void_var', p1=var_name)
            return
        if length <= 0:
            raise Exception('length of arrays must be at least one ')
        if len(function_memory) <= 0:
            array_pointer_address = new_symbol_table.get_new_global_address()
            allocation_address = new_symbol_table.allocate_array_memory(length)
            write_to_program_block(code="(ASSIGN, #%s, %s, )" % (allocation_address, array_pointer_address))
            symbol = Symbol(lexeme=var_name, var_type=(var_type + '*'), addressing_type='global',
                            address=array_pointer_address, scope=scope_stack[-1], symbol_type='variable')
        else:
            symbol = Symbol(lexeme=var_name, var_type=(var_type + "*"), addressing_type='relative',
                            address=function_memory[-1].frame_size, scope=scope_stack[-1], symbol_type='variable')
            pointer_address = get_by_relative_address(function_memory[-1].frame_size)
            function_memory[-1].frame_size += 4
            array_beginning_address = get_by_relative_address(function_memory[-1].frame_size)
            write_to_program_block(code='(ASSIGN, %s, %s, )' % (array_beginning_address[1:], pointer_address))
            function_memory[-1].frame_size += 4 * length
        new_symbol_table.define_symbol(symbol)
    elif action == '#array_access':
        array_symbol = semantic_stack[-2]
        if array_symbol.var_type != 'int*':
            raise Exception("accessing a non array variable as an array")
        offset_symbol = semantic_stack[-1]
        if offset_symbol.var_type != 'int':
            raise Exception("offset symbol is not of type int")
        array_pointer = get_symbol_address(array_symbol)
        offset = get_symbol_address(offset_symbol)
        semantic_stack.pop()
        semantic_stack.pop()
        relative_address = function_memory[-1].frame_size
        temp_address = get_by_relative_address(relative_address)
        semantic_stack.append(
            Symbol(lexeme="", var_type='int', addressing_type='relative pointer',
                   address=function_memory[-1].frame_size, scope=-1, symbol_type='variable')
        )
        function_memory[-1].frame_size += 4
        write_to_program_block(code="(ADD, %s, %s, %s)" % (array_pointer, offset, temp_address))
    elif action == '#push_number':
        num = re.match(r'\((\w+), (\d+)\)', label).group(2)
        temp_address = new_symbol_table.get_simple_temp()
        write_to_program_block(code="(ASSIGN, #%s, %d, )" % (num, temp_address))
        semantic_stack.append(
            Symbol(lexeme="", var_type='int', addressing_type='global', address=temp_address, scope=-1,
                   symbol_type='variable'))
    elif action == '#push_id':
        identifier = re.match(r'\((\w+), (\w+)\)', label).group(2)
        try:
            symbol = new_symbol_table.get_symbol(identifier)
            semantic_stack.append(symbol)
        except:
            semantic_check(check_error='undefined', p1=identifier)
            semantic_stack.append(None)
    elif action == '#multiply':
        SemanticChecker.check_that_are_int([semantic_stack[-2], semantic_stack[-1]])
        first_operand_address = get_symbol_address(semantic_stack[-1])
        second_operand_address = get_symbol_address(semantic_stack[-2])
        semantic_stack.pop()
        semantic_stack.pop()
        relative_address = function_memory[-1].frame_size
        temp_address = get_by_relative_address(relative_address)
        function_memory[-1].frame_size += 4
        write_to_program_block(
            code="(MULT, %s, %s, %s)" % (first_operand_address, second_operand_address, temp_address))
        semantic_stack.append(
            Symbol(lexeme="", var_type='int', addressing_type='relative', address=relative_address, scope=-1,
                   symbol_type='variable'))
    elif action == "#assign":
        destination = get_symbol_address(semantic_stack[-2])
        source = get_symbol_address(semantic_stack[-1])
        semantic_stack.pop()
        write_to_program_block(code="(ASSIGN, %s, %s, )" % (source, destination))
    elif action == '#pop':
        semantic_stack.pop()
    elif action == '#push_addition_operator':
        semantic_stack.append('ADD')
    elif action == '#push_subtraction_operator':
        semantic_stack.append('SUB')
    elif action == '#add_or_subtract':
        operator = semantic_stack[-2]
        SemanticChecker.check_that_are_int([semantic_stack[-3], semantic_stack[-1]])
        first_operand_address = get_symbol_address(semantic_stack[-3])
        second_operand_address = get_symbol_address(semantic_stack[-1])
        relative_address = function_memory[-1].frame_size
        address = get_by_relative_address(relative_address)
        function_memory[-1].frame_size += 4
        write_to_program_block(
            code="(%s, %s, %s, %s)" % (operator, first_operand_address, second_operand_address, address))
        semantic_stack.pop()
        semantic_stack.pop()
        semantic_stack.pop()
        semantic_stack.append(
            Symbol(lexeme="", var_type='int', addressing_type='relative', address=relative_address, scope=-1,
                   symbol_type='variable'))
    elif action == '#if':
        comparison_result_address = get_symbol_address(semantic_stack[-1])
        semantic_stack.pop()
        write_to_program_block(code="(JPF, %s, ?, )" % comparison_result_address)
        semantic_stack.append(program_block_counter - 1)
    elif action == '#else':
        write_to_program_block(code='(JP, ?, , )')
        if_condition_line = semantic_stack[-1]
        semantic_stack.pop()
        semantic_stack.append(program_block_counter - 1)
        edit_program_line(line=if_condition_line, replacement=str(program_block_counter))
    elif action == '#endif':
        if_body_jump_line = semantic_stack[-1]
        semantic_stack.pop()
        edit_program_line(line=if_body_jump_line, replacement=str(program_block_counter))
    elif action == '#start_repeat':
        repeat_until_scope_stack.append(ScopeEntry("repeat", len(semantic_stack)))
        write_to_program_block(code="(JP, %s, , )" % (program_block_counter + 2))
        semantic_stack.append(program_block_counter)
        write_to_program_block(code="(JP, ?, , )")
        semantic_stack.append(program_block_counter)
    elif action == '#repeat_condition':
        comparison_result_address = get_symbol_address(semantic_stack[-1])
        repeat_body_start_line = semantic_stack[-2]
        jump_out_line = semantic_stack[-3]
        semantic_stack.pop()
        semantic_stack.pop()
        semantic_stack.pop()
        write_to_program_block(code="(JPF, %s, %s, )" % (comparison_result_address, repeat_body_start_line))
        edit_program_line(jump_out_line, str(program_block_counter))
        repeat_until_scope_stack.pop()
    elif action == '#break':
        if len(repeat_until_scope_stack) == 0:
            semantic_check(check_error="break")
        else:
            last_scope = repeat_until_scope_stack[-1]
            semantic_stack_scope_index = last_scope.semantic_stack_start_index
            jump_out_line = semantic_stack[semantic_stack_scope_index]
            write_to_program_block(code="(JP, %s, , )" % jump_out_line)
    elif action == '#push_less_than_comparator':
        semantic_stack.append('LT')
    elif action == '#push_is_equal_comparator':
        semantic_stack.append('EQ')
    elif action == '#relop':
        SemanticChecker.check_that_are_int([semantic_stack[-3], semantic_stack[-1]])
        first_operand_address = get_symbol_address(semantic_stack[-3])
        operator = semantic_stack[-2]
        second_operand_address = get_symbol_address(semantic_stack[-1])
        relative_address = function_memory[-1].frame_size
        address = get_by_relative_address(relative_address)
        function_memory[-1].frame_size += 4
        write_to_program_block(
            code="(%s, %s, %s, %s)" % (operator, first_operand_address, second_operand_address, address))
        semantic_stack.pop()
        semantic_stack.pop()
        semantic_stack.pop()
        semantic_stack.append(
            Symbol(lexeme="", var_type='int', addressing_type='relative', address=relative_address, scope=-1,
                   symbol_type='variable'))
    elif action == '#negate':
        SemanticChecker.check_that_are_int([semantic_stack[-1]])
        first_operand_address = get_symbol_address(semantic_stack[-1])
        relative_address = function_memory[-1].frame_size
        result_address = get_by_relative_address(relative_address)
        function_memory[-1].frame_size += 4
        write_to_program_block(
            code="(MULT, %s, #-1, %s)" % (first_operand_address, result_address))
        semantic_stack.pop()
        semantic_stack.append(
            Symbol(lexeme="", var_type='int', addressing_type='relative', address=relative_address, scope=-1,
                   symbol_type='variable'))
