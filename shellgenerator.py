#!/usr/bin/python3 -tt

# Copyright 2012 Jussi Pakkanen

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os, stat
import interpreter

def shell_quote(cmdlist):
    return ["'" + x + "'" for x in cmdlist]

class ShellGenerator():
    
    def __init__(self, interpreter, environment):
        self.environment = environment
        self.interpreter = interpreter
        self.build_filename = 'compile.sh'
        self.processed_targets = {}

    def generate(self):
        self.interpreter.run()
        outfilename = os.path.join(self.environment.get_build_dir(), self.build_filename)
        outfile = open(outfilename, 'w')
        outfile.write('#!/bin/sh\n\n')
        outfile.write('echo This is an autogenerated shell script build file for project \\"%s\\".\n'
                      % self.interpreter.get_project())
        outfile.write('echo This is experimental and most likely will not work!\n')
        cdcmd = ['cd', self.environment.get_build_dir()]
        outfile.write(' '.join(shell_quote(cdcmd)) + '\n')
        self.generate_commands(outfile)
        outfile.close()
        os.chmod(outfilename, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC |\
                 stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

    def generate_single_compile(self, target, outfile, src):
        compiler = None
        for i in self.interpreter.compilers:
            if i.can_compile(src):
                compiler = i
                break
        if compiler is None:
            raise RuntimeError('No specified compiler can handle file ' + src)
        abs_src = os.path.join(self.environment.get_source_dir(), src)
        abs_obj = os.path.join(self.get_target_dir(target), src)
        abs_obj += '.' + self.environment.get_object_suffix()
        commands = []
        commands += compiler.get_exelist()
        commands += compiler.get_debug_flags()
        commands += compiler.get_std_warn_flags()
        commands += compiler.get_compile_only_flags()
        if isinstance(target, interpreter.SharedLibrary):
            commands += compiler.get_pic_flags()
        for dep in target.get_external_deps():
            commands += dep.get_compile_flags()
        commands.append(abs_src)
        commands += compiler.get_output_flags()
        commands.append(abs_obj)
        quoted = shell_quote(commands)
        outfile.write('\necho Compiling \\"%s\\"\n' % src)
        outfile.write(' '.join(quoted) + ' || exit\n')
        return abs_obj
    
    def build_target_link_arguments(self, deps):
        args = []
        for d in deps:
            if not isinstance(d, interpreter.StaticLibrary):
                print(d)
                raise RuntimeError('Only static libraries supported ATM.')
            args.append(self.get_target_filename(d))
        return args

    def generate_link(self, target, outfile, outname, obj_list):
        if isinstance(target, interpreter.StaticLibrary):
            linker = self.interpreter.static_linker
        else:
            linker = self.interpreter.compilers[0] # Fixme.
        commands = []
        commands += linker.get_exelist()
        if isinstance(target, interpreter.Executable):
            commands += linker.get_std_exe_link_flags()
        elif isinstance(target, interpreter.SharedLibrary):
            commands += linker.get_std_shared_lib_link_flags()
            commands += linker.get_pic_flags()
        elif isinstance(target, interpreter.StaticLibrary):
            commands += linker.get_std_link_flags()
        else:
            raise RuntimeError('Unknown build target type.')
        for dep in target.get_external_deps():
            commands += dep.get_link_flags()
        commands += linker.get_output_flags()
        commands.append(outname)
        commands += obj_list
        commands += self.build_target_link_arguments(target.get_dependencies())
        quoted = shell_quote(commands)
        outfile.write('\necho Linking \\"%s\\".\n' % target.get_basename())
        outfile.write(' '.join(quoted) + ' || exit\n')

    def get_target_dir(self, target):
        dirname = os.path.join(self.environment.get_build_dir(), target.get_basename())
        os.makedirs(dirname, exist_ok=True)
        return dirname

    def generate_commands(self, outfile):
        for i in self.interpreter.get_targets().items():
            target = i[1]
            self.generate_target(target, outfile)

    def process_target_dependencies(self, target, outfile):
        for t in target.get_dependencies():
            tname = t.get_basename()
            if not tname in self.processed_targets:
                self.generate_target(t, outfile)

    def get_target_filename(self, target):
        targetdir = self.get_target_dir(target)
        filename = os.path.join(targetdir, target.get_filename())
        return filename

    def generate_target(self, target, outfile):
        name = target.get_basename()
        if name in self.processed_targets:
            return
        self.process_target_dependencies(target, outfile)
        print('Generating target', name)
        outname = self.get_target_filename(target)
        obj_list = []
        for src in target.get_sources():
            obj_list.append(self.generate_single_compile(target, outfile, src))
        self.generate_link(target, outfile, outname, obj_list)
        self.processed_targets[name] = True

if __name__ == '__main__':
    code = """
    project('simple generator')
    language('c')
    executable('prog', 'prog.c', 'dep.c')
    """
    import environment
    os.chdir(os.path.split(__file__)[0])
    envir = environment.Environment('.', 'work area')
    intpr = interpreter.Interpreter(code, envir)
    g = ShellGenerator(intpr, envir)
    g.generate()
