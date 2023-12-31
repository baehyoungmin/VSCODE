# fibemu

More doc [here](https://forum.fibaro.com/topic/66394-visual-studio-code-vscode-for-quickapp-development/)

Steps to run

* Have python3 installed on your machine.
* pip install the needed python libraries from requirements.txt
 >pip install -r requirements.txt
* Create a config.json file with the credentials to access the HC3.
 See  config.json.example
* Install the vscode extension "Local Lua Debugger" by Tom Blind
* Create a QA file in the directory, select launcher "Fibenv QA file (remote)" and run debug F5
* See files in the examples/ directory

It's tested on MacOS and Windows 11.

All the emulator files lives in .vscode/emufiles/.

The trick here is that we have a python wrapper for the lua runtime so we solve dependencies on luasocket etc. and we don't need any special headers in the QA lua file to invoke/include the emulator/apis to make the QA being able to execute.

To give some hints to the emulator what type of QA we have etc. we can give directives similar to TQAE (but a bit different)
Ex.

```Lua
        --%%name=MyQA
        --%%type=com.fibaro.binarySwitch
        --%%file=qa3_1.lua,extra;
        --%%remote=devices:788,790
        --%%remote=globalVariables:myVar,anotherVar
        --%%debug=libraryfiles:false,userfilefiles:false

        function QuickApp:onInit()
          self:debug(self.name,self.type,self.id)
          fibaro.call(788,"turnOn")
        end
```

* --%%name sets the name of the QA
* --%%type sets the type of the QA
* --%%file includes extra QA files in the QA, libraries etc. In this example, 'qa3_1.lua' and the QA file will be named 'extra'
* --%%debug set some of the many debug flags
* --%%remote directive that instructs the emulator that it's ok to call device 788,789 on the HC3. As a default, the emulator treats all resources as local and we enable resources we want to interact with on the HC3 as 'remote'. This goes for other resources also like 'globalVariables'.

It integrates with the lua debugger so we can set breakpoints etc. 
Still work in progress but it's already really useful...
