# -*- coding: utf-8 -*-
import sys, os
class  Foo(object) :
      pass
class Bar( Foo ):
      def __init__( self ):
            super(Bar,  self).__init__(  )
x =dict()
y=  list()
z  =tuple()
s = set([])
f=frozenset([])
d ={'b':2,  'a' :  3}
v  ='{} {}'.format( os.sep,sys.path )
if  'a'  in d.keys()  :
      print(  'hello',x,y,z,s,f,d,v )
with open( 'file.txt' ,'r') as fh:
      print(  'data' ,fh.read( ))
def long_function(argument_one,  argument_two,argument_three,  argument_four,argument_five,  argument_six):
      return argument_one
