#!/usr/bin/python
"""
tbgen generates a blackbox VHDL teestbench from provided VHDL file(s)

Copyright(c) 2016 Harrison King Saturley-Hall

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in 
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all 
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

# Imports from STDLIB
import argparse, os, re, string, sys

# Elements included in the file dictionary
MODULE_GENERICS = "BLACKBOX_MODULE_GENERICS"
MODULE_INPUTS = "BLACKBOX_MODULE_INPUTS"
MODULE_OUTPUTS = "BLACKBOX_MODULE_OUTPUTS"
MODULE_CLOCK = "BLACKBOX_MODULE_CLOCK"

class FileExistsException(Exception):
    def __init__(
        self,
        value
    ):
        self.value = value

    def __str__( self ):
        return repr(self.value)


class FileArgumentParser(argparse.ArgumentParser):
    def __is_valid_file(
        self, 
        parser, 
        arg
    ):
        if not os.path.isfile(arg):
            parser.error('The file {} does not exist!'.format(arg))
        else:
            # File exists so return the filename
            return arg

    def __is_valid_directory(
        self,
        parser,
        arg
    ):
        if not os.path.isdir(arg):
            parser.error('The directory {} does not exist!'.format(arg))
        else:
            # File exists so return the directory
            return arg

    def add_argument_with_check(
        self, 
        *args, 
        **kwargs
    ):
        # Look for your FILE or DIR settings
        if 'metavar' in kwargs and 'type' not in kwargs:
            if kwargs['metavar'] is 'FILE':
                type=lambda x: self.__is_valid_file(self, x)
                kwargs['type'] = type
            elif kwargs['metavar'] is 'DIR':
                type=lambda x: self.__is_valid_directory(self, x)
                kwargs['type'] = type
        self.add_argument(*args, **kwargs)

def parse_file(
    f
):

    
    with open(f, 'r') as open_f:
        lines = list(open_f)
    
    doc = str.join('', lines).translate(
        string.maketrans(
            '\t\r\n',
            '   ', 
        ),
    )
    
    flags = re.IGNORECASE|re.X

    lib_regex = """
        (?<=library)
        \s+
        (?P<lib>
            \w+
        )
        \s*
        ;
        \s*
    """

    generic_regex = """
        (?P<generic_name>\w+) 
        \s* : \s* 
        (?P<generic_type>\w+) 
        (?:
            \s* := \s* 
            (?P<generic_value>\d+) 
        )?
        \s* ;? \s*
    """
 

    port_regex = """
        \s*
        (?P<port_name>
            \w+
        )
        \s* : \s* 
        (?P<port_direction>
            in|out|inout
        )
        \s* 
        (?P<port_type>
            STD_LOGIC
            (?:
                _VECTOR
                \s*
                \(
                    .+?
                \)
            )?
        )
        \s* 
        (?:
            := \s* 
            (?P<port_value>
                \(
                    .+?
                \) |
                .+
            )
            \s* 
        )? 
        ;?
        \s*
    """

    entity_regex = """
        (?<=entity) # entity keyword
        \s*
        (?P<entity> # name of the entity
            \w+
        ) 
        \s* is \s* # entity boilerplate
        (?: 
            generic \s* \( \s*
            (?P<generics>
                .*
            )
            \s* \) \s* ;
            \s* (?=port)
        )? # should match 0 or 1 times as generics are optional
        \s*
        (?: 
            port \s* \( \s*
            (?P<ports>
               .*
            )
            \s* \) \s* ;
        )
        \s*
        end \s* (?P=entity) \s* ;
    """ 

    # Find Library
    try:
        lib = re.search(
            lib_regex,
            doc,
            flags
        ).group('lib')
    except IndexError as E:
        raise IndexError('Failed to find the library.')

    # Find Imports
    imports = ["IEEE.STD_LOGIC_1164.ALL"]

    # Find Entity Name
    try:
        entity = re.search(
            entity_regex,
            doc,
            flags
        )
        entity_name  = entity.group('entity')
    except IndexError as E:
        raise IndexError('Failed to find the Entity Name.')

    # Find Generics 
    if entity.group('generics') is None:
        generics = None
    else:
        generics = []
        generics_list = entity.group(
            'generics'
        ).split(
            ';'
        )
        for generic in generics_list:
            generic_elements = re.search(
                generic_regex,
                generic,
                flags
            )
            generics.append(
               generic_elements.groupdict() 
            )
    
    # Find Entity Ports
    ports = []
    port_string = re.search(
        entity_regex,
        doc,
        flags
    ).group('ports')
    ports_list = port_string.split(";")
    for i, p in enumerate(ports_list):
        port_elements = re.search(
            port_regex,
            p,
            flags
        )
        ports.append(
            port_elements.groupdict()
        )

 
    return {
        'lib' : lib,
        'imports' : imports,
        'entity_name' : entity_name,
        'generics' : generics,
        'ports' : ports
    }

def write_tb(
    elements,
    abs_path,
    tb_name,
    clk_name,
):
    if os.path.exists(abs_path): # Raise an error that the file already exists
        raise FileExistsException("The testbench {} already exists. If you would like to generate an empty testbench for this entity move this existing testbench.".format(os.path.basename(abs_path)))

    # Make the string for imports
    import_string  = '\n'.join(
        [
            'USE %s;' % i 
            for i in elements['imports']
        ]
    )

    # Make the generic string
    if elements['generics'] is None:
        entity_generic_string = ''
    else:
        generics_string_list =  [
            "{0} : {1}{2}".format(
                g['generic_name'],
                g['generic_type'],
                ' := %s' % g['generic_value'].rstrip() if g['generic_value'] is not None else '',
            )
            for g in elements['generics']
        ]
        entity_generic_string = '\n\t\tGENERIC (\n{0}\n\t\t);'.format(
            ';\n'.join(
                [
                    '\t\t\t{0}'.format(
                        g
                    )
                    for g in generics_string_list
                ]
            )
        )

    
    # Make the ports string
    ports_string_list = [
        "\t\t\t{0} : {1} {2}{3}".format(
            p['port_name'],
            p['port_direction'],
            p['port_type'],
            ' := %s' % p['port_value'].rstrip() if p['port_value'] is not None else '',
        )
        for p in elements['ports']
    ]
    entity_port_string = ';\n'.join(
        ports_string_list
    )

    # Make the string to define the constants for the generics
    constant_string = '\tCONSTANT clk_period : TIME := 10 NS; -- Clock period definition\n'
    for g in generics_string_list:
        constant_string += '\tCONSTANT {0};\n'.format(
            g,
        )
        
    # Make the string to define the signals for the port signals
    port_signal_string = '\n'.join(
        [
            '\tSIGNAL {0} : {1}{2};'.format(
                p['port_name'],
                p['port_type'],
                ' := %s' % p['port_value'].rstrip() if p['port_value'] is not None else '',

            )
            for p in elements['ports']
        ]
    )

    # Make the string to define the generic mapping for the UUT
    uut_generic_map_string = ',\n'.join(
        [
            '\t\t{0} => {0}'.format(
                g['generic_name'],
            )
            for g in elements['generics']
        ]
    )
    if uut_generic_map_string != '':
        uut_generic_map_string = "\n\tGENERIC (\n{0}\n\t)".format(
            uut_generic_map_string,
        )

    # Make the string to define the port mapping for the UUT
    uut_port_map_string = ',\n'.join(
        [
            '\t\t{0} => {0}'.format(
                p['port_name'],
            )
            for p in elements['ports']
        ]
    )


    with open(abs_path, 'w') as f:
        f.write( 
"""LIBRARY {0};
USE {1}

ENTITY {2} IS
END {2};

ARCHITECTURE behavior of {2} IS

\t-- Component declaration for UUT
\tCOMPONENT {3}{4}
\t\tPORT (
{5}
\t\t);
\tEND COMPONENT;

\t-- Constants
{6}

\t-- Port signals
{7}

BEGIN
\t-- Instantiate the Unit Under Test (uut)
\tuut: {3}{8}
\tPORT (
{9}
\t);

\t-- Clock Process
\tclk_process : PROCESS
\tBEGIN
\t\t{10} <= '0';
\t\tWAIT FOR clk_period / 2;
\t\t{10} <= '1';
\t\tWAIT FOR clk_period / 2;
\tEND PROCESS;

\t--Stimulus Process
\tstim_proc : PROCESS
\t\t-- hold reset state for 100 ns.
\t\tWAIT FOR 100 NS;	

\t\tWAIT FOR clk_period * 10;

\t\t-- insert stimulus here


\t\tWAIT;
\tEND PROCESS;
END;""".format(
                elements['lib'], #0
                import_string, #1
                tb_name[:tb_name.rfind('.')], #2
                elements['entity_name'], #3
                entity_generic_string, #4
                entity_port_string, #5
                constant_string, #6
                port_signal_string, #7
                uut_generic_map_string, #8
                uut_port_map_string, #9
                clk_name, #10
            )
        )

    return 0

def cli():
    # Define the parser
    parser = FileArgumentParser(
        prog = 'tbGen',
        description = 'Create a VHDL blackbox testbench for a VHDL module'
    )

    # Add the Arguments
    parser.add_argument( # print the version of this code
        '-v',
        '--version',
        action='version', 
        version='%(prog)s 0.1'
    )
    
    parser.add_argument_with_check( # One or more files to serve as 
        'input',
        action = 'store',
        help = 'FILE or list of FILEs to process into empty testbenches',
        metavar='FILE',
        nargs = '+',
    )

    parser.add_argument( # the clock name if it exists
        '-c',
        '--clock',
        action = 'store',
        default = 'clk',
        dest = 'clock_name',
        help = 'The port name used for the clock. NOT FULLY IMPLEMENTED.',
        type = str
    )
    
    parser.add_argument( # the clock name if it exists
        '-d',
        '--delete',
        action = 'store_true', # Stores True if it is present
        default = False,
        dest = 'delete',
        help = 'If a file with the name as described for the testbench of the input file exists already, delete it.',
    )

    parser.add_argument_with_check( # Output location
        '-o',
        '--output_dir',
        action = 'store',
        default = '.',
        dest = 'dir',
        help = 'DIRECTORY in which to store the . Assumes that you have write access to this directory. Defaults to current directory.',
        metavar = 'DIR'
    )

    parser.add_argument( # filename replacement structure
        '-r',
        '--replace',
        default = '*_tb.vhd',
        dest = 'replacement',
        help = 'Filename format used for the testbench file. The loacation to put the input\'s filename without the file extension is denoted by an asterisk (*). Defaults to *_tb.vhd',
        type = str,
    )


    args = parser.parse_args()

    abs_path_replace = "{0}/%s".format(
        os.path.abspath(args.dir)
    )

    for f in args.input: # Process each file
        try:
            elements = parse_file(f)

# DEBUGGING
#            print f
#            print elements
#            for k in elements.keys():
#                print "  %s => %s" % (k, elements[k])

            tb_filename = args.replacement.replace(
                "*", 
                os.path.basename(f).split(".")[0]
            )

            abs_path = abs_path_replace % (
                tb_filename    
            )

            # Delete the filename if argument is specified
            if args.delete and os.path.exists(abs_path):
                os.remove(abs_path)

            success = write_tb(
                elements,
                abs_path,
                tb_filename,
                args.clock_name
            )
            print("Success writing testbench {0} for {1}".format(
                    tb_filename,
                    f
                )
            )
        except FileExistsException as E:
            print(E)
            print("Continuing with the next document.")
        except AttributeError as E:
            print(E)
            print("Continuing with the next document.")

    return 0

if __name__ == '__main__':
    cli()
